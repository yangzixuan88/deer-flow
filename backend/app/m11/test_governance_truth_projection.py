import copy
import inspect
import json

from backend.app.m11 import governance_bridge


def _write_state(path, records):
    path.write_text(
        json.dumps({"outcome_records": records}, ensure_ascii=False),
        encoding="utf-8",
    )


def test_project_truth_state_does_not_mutate_input_record():
    record = {
        "outcome_type": "sandbox_execution_result",
        "actual": 1.0,
        "predicted": 0.8,
        "context": {"candidate_id": "c1", "verify_exit_code": 0},
    }
    original = copy.deepcopy(record)

    projection = governance_bridge.project_truth_state(record)

    assert record == original
    assert projection["truth_events"]


def test_sandbox_execution_result_projects_execution_truth():
    record = {
        "outcome_type": "sandbox_execution_result",
        "actual": 1.0,
        "context": {"candidate_id": "c2", "verify_exit_code": 0},
    }

    projection = governance_bridge.project_truth_state(record)

    assert any(
        event["truth_track"] == "execution_truth"
        and event["truth_type"] == "actual_outcome"
        for event in projection["truth_events"]
    )


def test_observation_pool_actual_half_not_execution_success_rate(tmp_path, monkeypatch):
    state_path = tmp_path / "governance_state.json"
    _write_state(
        state_path,
        [
            {
                "outcome_type": "upgrade_center_execution_result",
                "actual": 0.5,
                "predicted": 0.75,
                "context": {"candidate_id": "c3", "filter_result": "observation_pool"},
            }
        ],
    )
    monkeypatch.setattr(governance_bridge, "_STATE_FILE", state_path)

    result = governance_bridge.get_success_rate_candidates("execution_success_rate")

    assert result["eligible_count"] == 0
    assert result["ineligible_count"] >= 1
    assert any("not_execution_truth:observation_truth" in key for key in result["excluded_reasons"])


def test_approval_decision_not_execution_success_rate(tmp_path, monkeypatch):
    state_path = tmp_path / "governance_state.json"
    _write_state(
        state_path,
        [
            {
                "outcome_type": "upgrade_center_approval",
                "actual": 1.0,
                "predicted": 0.75,
                "context": {"candidate_id": "c4", "requires_approval": True},
            }
        ],
    )
    monkeypatch.setattr(governance_bridge, "_STATE_FILE", state_path)

    result = governance_bridge.get_success_rate_candidates("execution_success_rate")

    assert result["eligible_count"] == 0
    assert any("not_execution_truth:governance_truth" in key for key in result["excluded_reasons"])


def test_unknown_outcome_does_not_raise():
    projection = governance_bridge.project_truth_state(
        {"outcome_type": "unknown_outcome", "actual": 1.0, "context": {}}
    )

    assert projection["truth_events"] == []
    assert projection["state_events"] == []
    assert projection["warnings"]


def test_project_recent_outcomes_reads_tmp_state_only(tmp_path, monkeypatch):
    state_path = tmp_path / "governance_state.json"
    _write_state(
        state_path,
        [
            {
                "outcome_type": "sandbox_execution_result",
                "actual": 1.0,
                "context": {"candidate_id": "c5", "verify_exit_code": 0},
            },
            {
                "outcome_type": "upgrade_queue_snapshot",
                "context": {"tasks": [{"candidate_id": "c6", "status": "running"}]},
            },
        ],
    )
    before = state_path.read_text(encoding="utf-8")
    monkeypatch.setattr(governance_bridge, "_STATE_FILE", state_path)

    result = governance_bridge.project_recent_outcomes(limit=20)

    assert result["total_scanned"] == 2
    assert result["truth_events_count"] >= 1
    assert result["state_events_count"] >= 1
    assert state_path.read_text(encoding="utf-8") == before


def test_project_recent_outcomes_large_limit_is_capped(tmp_path, monkeypatch):
    state_path = tmp_path / "governance_state.json"
    records = [
        {
            "outcome_type": "sandbox_execution_result",
            "actual": 1.0,
            "context": {"candidate_id": f"c{i}", "verify_exit_code": 0},
        }
        for i in range(250)
    ]
    _write_state(state_path, records)
    monkeypatch.setattr(governance_bridge, "_STATE_FILE", state_path)

    result = governance_bridge.project_recent_outcomes(limit=999)

    assert result["total_scanned"] == 200
    assert result["projected_count"] == 200


def test_get_success_rate_candidates_returns_only_execution_truth(tmp_path, monkeypatch):
    state_path = tmp_path / "governance_state.json"
    _write_state(
        state_path,
        [
            {
                "outcome_type": "sandbox_execution_result",
                "actual": 1.0,
                "context": {"candidate_id": "c7", "verify_exit_code": 0},
            },
            {
                "outcome_type": "upgrade_center_execution_result",
                "actual": 0.5,
                "context": {"candidate_id": "c8", "filter_result": "observation_pool"},
            },
            {
                "outcome_type": "asset_promotion",
                "context": {"asset_id": "a1", "score": 0.91},
            },
        ],
    )
    monkeypatch.setattr(governance_bridge, "_STATE_FILE", state_path)

    result = governance_bridge.get_success_rate_candidates("execution_success_rate")

    assert result["eligible_count"] == 1
    assert all(event["truth_track"] == "execution_truth" for event in result["eligible_events"])


def test_malformed_governance_state_returns_warning(tmp_path, monkeypatch):
    state_path = tmp_path / "governance_state.json"
    state_path.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(governance_bridge, "_STATE_FILE", state_path)

    result = governance_bridge.project_recent_outcomes()

    assert result["warnings"]
    assert result["projected_count"] == 0


def test_record_outcome_importable_and_signature_unchanged():
    assert hasattr(governance_bridge.GovernanceBridge, "record_outcome")
    signature = inspect.signature(governance_bridge.GovernanceBridge.record_outcome)

    assert list(signature.parameters) == [
        "self",
        "outcome_type",
        "actual_result",
        "predicted_result",
        "context",
    ]
