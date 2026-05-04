import json
import sys
from pathlib import Path

sys.path.insert(0, ".")


def test_infer_primary_mode_hint_explicit_selected_mode_hint():
    from app.gateway.mode_instrumentation import infer_primary_mode_hint

    result = infer_primary_mode_hint({"selected_mode_hint": "workflow"})
    assert result["primary_mode"] == "workflow"
    assert result["confidence"] >= 0.9


def test_infer_roundtable_rtcm_hint():
    from app.gateway.mode_instrumentation import infer_primary_mode_hint

    result = infer_primary_mode_hint({"message": "Need RTCM council review"})
    assert result["primary_mode"] == "roundtable"


def test_infer_workflow_hint():
    from app.gateway.mode_instrumentation import infer_primary_mode_hint

    result = infer_primary_mode_hint({"message": "Run this workflow pipeline"})
    assert result["primary_mode"] == "workflow"


def test_infer_autonomous_hint():
    from app.gateway.mode_instrumentation import infer_primary_mode_hint

    result = infer_primary_mode_hint({"message": "Use an autonomous agent for this long-running task"})
    assert result["primary_mode"] == "autonomous_agent"


def test_infer_search_hint():
    from app.gateway.mode_instrumentation import infer_primary_mode_hint

    result = infer_primary_mode_hint({"message": "Search evidence and citations"})
    assert result["primary_mode"] == "search"


def test_infer_task_fix_test_hint():
    from app.gateway.mode_instrumentation import infer_primary_mode_hint

    result = infer_primary_mode_hint({"message": "Fix and test the build"})
    assert result["primary_mode"] == "task"


def test_unknown_payload_low_confidence_direct_answer():
    from app.gateway.mode_instrumentation import infer_primary_mode_hint

    result = infer_primary_mode_hint({"message": "hello"})
    assert result["primary_mode"] in {"direct_answer", "unknown"}
    assert result["confidence"] < 0.5


def test_create_gateway_mode_instrumentation_creates_mode_session():
    from app.gateway.mode_instrumentation import create_gateway_mode_instrumentation

    result = create_gateway_mode_instrumentation({"message": "fix test"})
    assert result["instrumentation_only"] is True
    assert result["mode_session"]["mode_session_id"].startswith("modesess_")
    assert result["primary_mode"] == "task"


def test_context_request_thread_id_passthrough():
    from app.gateway.mode_instrumentation import create_gateway_mode_instrumentation

    context = {"context_id": "ctx1", "request_id": "req1", "thread_id": "thread1"}
    result = create_gateway_mode_instrumentation({"message": "search"}, context)
    assert result["context_id"] == "ctx1"
    assert result["request_id"] == "req1"
    assert result["thread_id"] == "thread1"
    assert result["mode_session"]["context_id"] == "ctx1"


def test_attach_mode_metadata_to_context_does_not_mutate_original():
    from app.gateway.mode_instrumentation import (
        attach_mode_metadata_to_context,
        create_gateway_mode_instrumentation,
    )

    context = {"context_id": "ctx1", "request_id": "req1"}
    original = dict(context)
    metadata = create_gateway_mode_instrumentation({"message": "search"}, context)
    attached = attach_mode_metadata_to_context(context, metadata)
    assert context == original
    assert attached["mode_session_id"] == metadata["mode_session"]["mode_session_id"]
    assert attached["mode_metadata"]["instrumentation_only"] is True


def test_build_gateway_mode_call_graph_projection_no_invocation():
    from app.gateway.mode_instrumentation import (
        build_gateway_mode_call_graph_projection,
        create_gateway_mode_instrumentation,
    )

    metadata = create_gateway_mode_instrumentation({"message": "search"})
    graph = build_gateway_mode_call_graph_projection(metadata)
    assert graph["mode_session_id"] == metadata["mode_session"]["mode_session_id"]
    assert len(graph["nodes"]) == 1
    assert graph["edges"] == []


def test_generate_gateway_mode_instrumentation_sample_writes_tmp_path(tmp_path):
    from app.gateway.mode_instrumentation import generate_gateway_mode_instrumentation_sample

    output = tmp_path / "sample.json"
    result = generate_gateway_mode_instrumentation_sample(str(output))
    assert output.exists()
    data = json.loads(output.read_text(encoding="utf-8"))
    assert result["output_path"] == str(output)
    assert data["mode_instrumentation"]["instrumentation_only"] is True
    assert "mode_call_graph_projection" in data


def test_no_m01_m04_rtcm_gateway_run_called(monkeypatch):
    import app.gateway.mode_instrumentation as mi

    touched = {"external": False}

    def fail_if_called(*args, **kwargs):
        touched["external"] = True
        raise AssertionError("external runtime path should not be called")

    monkeypatch.setattr(mi, "build_mode_call_graph", mi.build_mode_call_graph)
    result = mi.create_gateway_mode_instrumentation({"message": "task fix"})
    assert result["primary_mode"] == "task"
    assert touched["external"] is False
    assert not hasattr(mi, "start_run")
    assert not hasattr(mi, "IntentClassifier")
    assert not hasattr(mi, "Coordinator")


def test_existing_context_envelope_still_round_trips():
    from app.gateway.context import ContextEnvelope

    env = ContextEnvelope(context_id="ctx", request_id="req", thread_id="thread")
    data = env.to_dict()
    restored = ContextEnvelope.from_dict(data)
    assert restored.context_id == "ctx"
    assert restored.request_id == "req"
    assert restored.thread_id == "thread"


def test_sample_does_not_write_runtime_dirs(tmp_path):
    from app.gateway.mode_instrumentation import generate_gateway_mode_instrumentation_sample

    output = tmp_path / "only_report_sample.json"
    generate_gateway_mode_instrumentation_sample(str(output))
    assert output.exists()
    assert sorted(path.name for path in tmp_path.iterdir()) == ["only_report_sample.json"]
