import json
import sys

sys.path.insert(0, ".")


def _event():
    from app.tool_runtime.tool_runtime_contract import create_tool_execution_event

    return create_tool_execution_event("fs.edit", "edit_code", "test", {"tool_type": "file_system"})


def _mode_invocation():
    return {
        "mode_invocation_id": "modeinv_1",
        "mode_session_id": "modesess_1",
        "from_mode": "task",
        "to_mode": "search",
    }


def _context():
    return {"context_id": "ctx_1", "request_id": "req_1", "thread_id": "thread_1"}


def test_link_tool_event_to_mode_invocation_does_not_mutate_event():
    from app.tool_runtime.tool_runtime_projection import link_tool_event_to_mode_invocation

    event = _event()
    original = dict(event)
    result = link_tool_event_to_mode_invocation(event, _mode_invocation(), context_envelope=_context())
    assert event == original
    assert result["linked_event"] != event


def test_link_extracts_mode_invocation_fields():
    from app.tool_runtime.tool_runtime_projection import link_tool_event_to_mode_invocation

    result = link_tool_event_to_mode_invocation(_event(), _mode_invocation(), context_envelope=_context())
    linked = result["linked_event"]
    assert linked["mode_session_id"] == "modesess_1"
    assert linked["mode_invocation_id"] == "modeinv_1"
    assert linked["caller_mode"] == "task"


def test_link_extracts_context_fields():
    from app.tool_runtime.tool_runtime_projection import link_tool_event_to_mode_invocation

    result = link_tool_event_to_mode_invocation(_event(), _mode_invocation(), context_envelope=_context())
    linked = result["linked_event"]
    assert linked["context_id"] == "ctx_1"
    assert linked["request_id"] == "req_1"
    assert linked["thread_id"] == "thread_1"


def test_missing_mode_invocation_warns_not_fail():
    from app.tool_runtime.tool_runtime_projection import link_tool_event_to_mode_invocation

    result = link_tool_event_to_mode_invocation(_event(), None, context_envelope=_context())
    assert "missing_mode_invocation" in result["warnings"]
    assert result["linked_event"]["context_id"] == "ctx_1"


def test_create_contextual_tool_event_does_not_execute_tool():
    from app.tool_runtime.tool_runtime_projection import create_contextual_tool_event

    result = create_contextual_tool_event(
        "claude.code",
        "claude_code_call",
        "test",
        "claude_code",
        mode_invocation=_mode_invocation(),
        context_envelope=_context(),
    )
    assert result["tool_event"]["status"] == "planned"
    assert result["tool_event"]["success"] is None


def test_create_contextual_tool_event_preserves_backup_rollback():
    from app.tool_runtime.tool_runtime_projection import create_contextual_tool_event

    result = create_contextual_tool_event(
        "config",
        "modify_config",
        "test",
        "file_system",
        mode_invocation=_mode_invocation(),
        context_envelope=_context(),
        metadata={"target_path": "package.json", "backup_refs": ["b"], "rollback_refs": ["r"]},
    )
    assert result["tool_event"]["backup_refs"] == ["b"]
    assert result["tool_event"]["rollback_refs"] == ["r"]


def test_create_contextual_tool_event_returns_policy_validation():
    from app.tool_runtime.tool_runtime_projection import create_contextual_tool_event

    result = create_contextual_tool_event(
        "edit",
        "edit_code",
        "test",
        "file_system",
        mode_invocation=_mode_invocation(),
        context_envelope=_context(),
    )
    assert "policy_validation" in result
    assert "root_guard_required_but_missing" in result["policy_validation"]["warnings"]


def test_project_tool_events_for_mode_callgraph_by_invocation():
    from app.tool_runtime.tool_runtime_projection import (
        create_contextual_tool_event,
        project_tool_events_for_mode_callgraph,
    )

    projected = create_contextual_tool_event("read", "read_file", "test", "file_system", _mode_invocation(), context_envelope=_context())
    result = project_tool_events_for_mode_callgraph([projected["tool_event"]])
    assert result["by_mode_invocation_id"]["modeinv_1"] == 1


def test_project_tool_events_for_mode_callgraph_orphans():
    from app.tool_runtime.tool_runtime_projection import project_tool_events_for_mode_callgraph

    result = project_tool_events_for_mode_callgraph([_event()])
    assert len(result["orphan_tool_events"]) == 1
    assert "orphan_tool_events_detected" in result["warnings"]


def test_project_gateway_tool_runtime_empty_planned_calls():
    from app.tool_runtime.tool_runtime_projection import project_gateway_tool_runtime

    result = project_gateway_tool_runtime({"message": "search"}, _context(), [])
    assert result["tool_events"] == []
    assert result["summary"]["total_events"] == 0


def test_project_gateway_tool_runtime_generates_contextual_events():
    from app.tool_runtime.tool_runtime_projection import project_gateway_tool_runtime

    result = project_gateway_tool_runtime(
        {"message": "fix test"},
        _context(),
        [{"tool_id": "fs.read", "tool_type": "file_system", "operation_type": "read_file"}],
    )
    assert len(result["tool_events"]) == 1
    assert result["tool_events"][0]["context_id"] == "ctx_1"
    assert result["tool_events"][0]["mode_session_id"] == result["mode_metadata"]["mode_session"]["mode_session_id"]


def test_detect_tool_mode_risks_level_3_confirmation():
    from app.tool_runtime.tool_runtime_projection import detect_tool_mode_risks, project_gateway_tool_runtime

    projection = project_gateway_tool_runtime(
        {"message": "task"},
        _context(),
        [{"tool_id": "delete", "tool_type": "file_system", "operation_type": "delete_file"}],
    )
    risks = detect_tool_mode_risks(projection)
    assert "level_3_requires_confirmation" in risks["risk_by_type"]


def test_detect_tool_mode_risks_prompt_replace_missing_rollback():
    from app.tool_runtime.tool_runtime_projection import detect_tool_mode_risks, project_gateway_tool_runtime

    projection = project_gateway_tool_runtime(
        {"message": "task"},
        _context(),
        [{"tool_id": "prompt", "tool_type": "file_system", "operation_type": "prompt_replace"}],
    )
    risks = detect_tool_mode_risks(projection)
    assert "prompt_replace_without_rollback" in risks["risk_by_type"]


def test_detect_tool_mode_risks_autonomous_high_risk():
    from app.tool_runtime.tool_runtime_projection import detect_tool_mode_risks, project_gateway_tool_runtime

    projection = project_gateway_tool_runtime(
        {"message": "autonomous agent should modify config"},
        _context(),
        [{"tool_id": "config", "tool_type": "file_system", "operation_type": "modify_config", "metadata": {"target_path": "package.json"}}],
    )
    risks = detect_tool_mode_risks(projection)
    assert "autonomous_agent_high_risk_tool" in risks["risk_by_type"]


def test_generate_tool_gateway_mode_projection_sample_writes_tmp_path(tmp_path):
    from app.tool_runtime.tool_runtime_projection import generate_tool_gateway_mode_projection_sample

    output = tmp_path / "sample.json"
    result = generate_tool_gateway_mode_projection_sample(str(output))
    assert result["output_path"] == str(output)
    assert output.exists()
    data = json.loads(output.read_text(encoding="utf-8"))
    assert len(data["contextual_tool_events"]) == 5
    assert sorted(path.name for path in tmp_path.iterdir()) == ["sample.json"]


def test_no_real_shell_mcp_claude_opencli_calls():
    import app.tool_runtime.tool_runtime_projection as projection

    result = projection.project_gateway_tool_runtime(
        {"message": "autonomous"},
        _context(),
        [{"tool_id": "claude.code", "tool_type": "claude_code", "operation_type": "claude_code_call"}],
    )
    assert result["tool_events"][0]["status"] == "planned"
    assert not hasattr(projection, "subprocess")
    assert not hasattr(projection, "opencli")
    assert not hasattr(projection, "mcp_client")


def test_no_governance_memory_asset_prompt_runtime_write(tmp_path):
    from app.tool_runtime.tool_runtime_projection import generate_tool_gateway_mode_projection_sample

    output = tmp_path / "sample.json"
    generate_tool_gateway_mode_projection_sample(str(output))
    assert sorted(path.name for path in tmp_path.iterdir()) == ["sample.json"]


def test_gateway_response_not_changed():
    from app.gateway.context import ContextEnvelope
    from app.tool_runtime.tool_runtime_projection import project_gateway_tool_runtime

    context = ContextEnvelope(context_id="ctx", request_id="req", thread_id="thread").to_dict()
    original_keys = set(context.keys())
    project_gateway_tool_runtime({"message": "search"}, context, [])
    assert set(context.keys()) == original_keys
