from backend.app.m11.truth_state_contract import (
    is_success_rate_eligible,
    map_legacy_outcome_to_state_events,
    map_legacy_outcome_to_truth_events,
    summarize_outcome_contract,
)


def _event(events, truth_type):
    return next(event for event in events if event["truth_type"] == truth_type)


def test_sandbox_execution_success_maps_to_execution_actual_outcome():
    record = {
        "outcome_type": "sandbox_execution_result",
        "actual": 1.0,
        "predicted": 0.8,
        "context": {"candidate_id": "c1", "verify_exit_code": 0},
    }

    event = _event(map_legacy_outcome_to_truth_events(record), "actual_outcome")

    assert event["truth_track"] == "execution_truth"
    assert event["actual_value"] == 1.0
    assert event["subject_id"] == "c1"


def test_sandbox_execution_failure_maps_to_execution_actual_outcome():
    record = {
        "outcome_type": "sandbox_execution_result",
        "actual": 0.0,
        "context": {"candidate_id": "c1", "verify_exit_code": 1},
    }

    event = _event(map_legacy_outcome_to_truth_events(record), "actual_outcome")

    assert event["truth_track"] == "execution_truth"
    assert event["actual_value"] == 0.0


def test_sandbox_execution_truth_is_execution_success_rate_eligible():
    record = {
        "outcome_type": "sandbox_execution_result",
        "actual": 1.0,
        "context": {"candidate_id": "c1", "verify_exit_code": 0},
    }
    event = _event(map_legacy_outcome_to_truth_events(record), "actual_outcome")

    assert is_success_rate_eligible(event, "execution_success_rate") is True


def test_observation_pool_actual_half_maps_to_observation_signal():
    record = {
        "outcome_type": "upgrade_center_execution_result",
        "actual": 0.5,
        "predicted": 0.75,
        "context": {"candidate_id": "c2", "filter_result": "observation_pool"},
    }

    event = _event(map_legacy_outcome_to_truth_events(record), "observation_signal")

    assert event["truth_track"] == "observation_truth"
    assert event["actual_value"] == 0.5


def test_observation_signal_not_execution_success_rate_eligible():
    record = {
        "outcome_type": "upgrade_center_execution_result",
        "actual": 0.5,
        "predicted": 0.75,
        "context": {"candidate_id": "c2", "filter_result": "observation_pool"},
    }
    event = _event(map_legacy_outcome_to_truth_events(record), "observation_signal")

    assert is_success_rate_eligible(event, "execution_success_rate") is False


def test_upgrade_center_execution_actual_one_maps_to_governance_approval():
    record = {
        "outcome_type": "upgrade_center_execution_result",
        "actual": 1.0,
        "predicted": 0.9,
        "context": {"candidate_id": "c3", "filter_result": "deep_analysis_pool"},
    }

    event = _event(map_legacy_outcome_to_truth_events(record), "approval_decision")

    assert event["truth_track"] == "governance_truth"
    assert event["actual_value"] == 1.0


def test_approval_decision_not_execution_success_rate_eligible():
    record = {
        "outcome_type": "upgrade_center_approval",
        "actual": 1.0,
        "predicted": 0.75,
        "context": {"candidate_id": "c4", "requires_approval": True},
    }
    event = _event(map_legacy_outcome_to_truth_events(record), "approval_decision")

    assert is_success_rate_eligible(event, "execution_success_rate") is False


def test_predicted_field_maps_to_predicted_outcome():
    record = {
        "outcome_type": "sandbox_execution_result",
        "actual": 1.0,
        "predicted": 0.8,
        "context": {"candidate_id": "c5", "verify_exit_code": 0},
    }

    event = _event(map_legacy_outcome_to_truth_events(record), "predicted_outcome")

    assert event["truth_type"] == "predicted_outcome"
    assert event["predicted_value"] == 0.8


def test_asset_promotion_score_maps_to_asset_quality_signal():
    record = {
        "outcome_type": "asset_promotion",
        "actual": 1.0,
        "context": {"asset_id": "a1", "score": 0.91, "tier": "premium"},
    }

    event = _event(map_legacy_outcome_to_truth_events(record), "asset_quality_signal")

    assert event["truth_track"] == "asset_truth"
    assert event["actual_value"] == 0.91
    assert is_success_rate_eligible(event, "asset_quality_score") is True


def test_asset_quality_signal_not_execution_success_rate_eligible():
    record = {
        "outcome_type": "asset_promotion",
        "context": {"asset_id": "a1", "score": 0.91},
    }
    event = _event(map_legacy_outcome_to_truth_events(record), "asset_quality_signal")

    assert is_success_rate_eligible(event, "execution_success_rate") is False


def test_upgrade_queue_snapshot_maps_to_experiment_queue_task_state():
    record = {
        "outcome_type": "upgrade_queue_snapshot",
        "context": {"tasks": [{"candidate_id": "c6", "status": "running"}]},
    }

    event = map_legacy_outcome_to_state_events(record)[0]

    assert event["state_domain"] == "experiment_queue_task"
    assert event["subject_id"] == "c6"
    assert event["new_state"] == "running"


def test_unknown_outcome_type_does_not_raise_and_returns_empty():
    record = {"outcome_type": "unknown_outcome", "actual": 1.0, "context": {}}

    assert map_legacy_outcome_to_truth_events(record) == []
    assert map_legacy_outcome_to_state_events(record) == []


def test_summarize_outcome_contract_returns_warnings_and_classification():
    record = {
        "outcome_type": "upgrade_center_execution_result",
        "actual": 0.5,
        "predicted": 0.75,
        "context": {"candidate_id": "c7", "filter_result": "observation_pool"},
    }

    summary = summarize_outcome_contract(record)

    assert summary["legacy_outcome_type"] == "upgrade_center_execution_result"
    assert summary["truth_events_count"] >= 1
    assert "execution_success_rate" not in summary["success_rate_eligible_scopes"]
    assert summary["warnings"]
    assert summary["semantic_classification"]["has_observation_signal"] is True
