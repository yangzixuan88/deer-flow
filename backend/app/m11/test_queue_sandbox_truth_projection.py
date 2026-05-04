import json
from pathlib import Path

from backend.app.m11 import queue_sandbox_truth_projection as projection


def test_load_experiment_queue_snapshot_missing_file_returns_warning(tmp_path):
    missing = tmp_path / "missing_queue.json"

    result = projection.load_experiment_queue_snapshot(str(missing))

    assert result["exists"] is False
    assert result["warnings"]


def test_load_experiment_queue_snapshot_malformed_json_returns_warning(tmp_path):
    queue_path = tmp_path / "experiment_queue.json"
    queue_path.write_text("{bad json", encoding="utf-8")

    result = projection.load_experiment_queue_snapshot(str(queue_path))

    assert result["exists"] is True
    assert result["task_count"] == 0
    assert result["warnings"]


def test_load_experiment_queue_snapshot_counts_task_status(tmp_path):
    queue_path = tmp_path / "experiment_queue.json"
    queue_path.write_text(
        json.dumps(
            {
                "tasks": [
                    {"candidate_id": "c1", "status": "pending"},
                    {"candidate_id": "c2", "status": "completed", "verify_script_path": "checks/a.py"},
                    {"candidate_id": "c3", "status": "failed", "verify_script_path": "checks/b.py"},
                ]
            }
        ),
        encoding="utf-8",
    )

    result = projection.load_experiment_queue_snapshot(str(queue_path))

    assert result["task_count"] == 3
    assert result["status_counts"] == {"pending": 1, "completed": 1, "failed": 1}
    assert result["with_verify_script_count"] == 2


def test_project_sandbox_outcomes_counts_pass_fail_with_monkeypatch(monkeypatch):
    monkeypatch.setattr(
        projection,
        "project_recent_outcomes",
        lambda limit=100, outcome_type=None: {
            "total_scanned": 2,
            "truth_events_count": 4,
            "state_events_count": 2,
            "warnings": [],
        },
    )
    records = [
        {"outcome_type": "sandbox_execution_result", "actual": 1.0, "context": {"candidate_id": "c1", "verify_exit_code": 0}},
        {"outcome_type": "sandbox_execution_result", "actual": 0.0, "context": {"candidate_id": "c2", "verify_exit_code": 1}},
    ]
    monkeypatch.setattr(projection, "_load_recent_sandbox_records", lambda limit: (records, []))

    result = projection.project_sandbox_outcomes()

    assert result["sandbox_records_count"] == 2
    assert result["execution_truth_count"] == 2
    assert result["actual_pass_count"] == 1
    assert result["actual_fail_count"] == 1


def test_project_sandbox_outcomes_does_not_count_governance_truth(monkeypatch):
    monkeypatch.setattr(
        projection,
        "project_recent_outcomes",
        lambda limit=100, outcome_type=None: {"total_scanned": 1, "truth_events_count": 1, "state_events_count": 0, "warnings": []},
    )
    monkeypatch.setattr(
        projection,
        "_load_recent_sandbox_records",
        lambda limit: ([{"outcome_type": "upgrade_center_approval", "actual": 1.0, "context": {"candidate_id": "c1"}}], []),
    )

    result = projection.project_sandbox_outcomes()

    assert result["execution_truth_count"] == 0
    assert result["actual_pass_count"] == 0


def test_get_sandbox_execution_success_candidates_only_counts_execution_truth(monkeypatch):
    monkeypatch.setattr(
        projection,
        "get_success_rate_candidates",
        lambda metric_scope, limit=100: {
            "eligible_events": [
                {"truth_track": "execution_truth", "truth_type": "actual_outcome", "actual_value": 1.0},
                {"truth_track": "governance_truth", "truth_type": "approval_decision", "actual_value": 1.0},
            ],
            "excluded_reasons": {"not_execution_truth:governance_truth": 1},
            "warnings": [],
        },
    )

    result = projection.get_sandbox_execution_success_candidates()

    assert result["eligible_count"] == 1
    assert result["pass_count"] == 1


def test_simple_success_rate_calculation(monkeypatch):
    monkeypatch.setattr(
        projection,
        "get_success_rate_candidates",
        lambda metric_scope, limit=100: {
            "eligible_events": [
                {"truth_track": "execution_truth", "truth_type": "actual_outcome", "actual_value": 1.0},
                {"truth_track": "execution_truth", "truth_type": "actual_outcome", "actual_value": 0.0},
                {"truth_track": "execution_truth", "truth_type": "actual_outcome", "actual_value": 1.0},
            ],
            "excluded_reasons": {},
            "warnings": [],
        },
    )

    result = projection.get_sandbox_execution_success_candidates()

    assert result["pass_count"] == 2
    assert result["fail_count"] == 1
    assert result["simple_success_rate"] == 2 / 3


def test_correlate_queue_with_sandbox_truth_candidate_id(tmp_path, monkeypatch):
    queue_path = tmp_path / "experiment_queue.json"
    queue_path.write_text(
        json.dumps({"tasks": [{"candidate_id": "c1", "status": "completed", "verify_script_path": "checks/a.py"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        projection,
        "project_sandbox_outcomes",
        lambda limit=100: {
            "execution_truth_count": 1,
            "truth_events": [
                {
                    "truth_track": "execution_truth",
                    "truth_type": "actual_outcome",
                    "subject_id": "c1",
                    "predicted_value": 0.8,
                    "evidence_refs": [{"key": "candidate_id", "value": "c1"}],
                }
            ],
            "warnings": [],
        },
    )

    result = projection.correlate_queue_with_sandbox_truth(str(queue_path))

    assert result["queue_verify_without_sandbox_truth_count"] == 0
    assert result["sandbox_truth_without_queue_task_count"] == 0
    assert result["sandbox_predicted_present_count"] == 1


def test_correlate_queue_with_sandbox_truth_mismatch_warning(tmp_path, monkeypatch):
    queue_path = tmp_path / "experiment_queue.json"
    queue_path.write_text(
        json.dumps({"tasks": [{"candidate_id": "queue-only", "status": "pending", "verify_script_path": "checks/a.py"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        projection,
        "project_sandbox_outcomes",
        lambda limit=100: {
            "execution_truth_count": 1,
            "truth_events": [
                {
                    "truth_track": "execution_truth",
                    "truth_type": "actual_outcome",
                    "subject_id": "truth-only",
                    "predicted_value": None,
                    "evidence_refs": [{"key": "candidate_id", "value": "truth-only"}],
                }
            ],
            "warnings": [],
        },
    )

    result = projection.correlate_queue_with_sandbox_truth(str(queue_path))

    assert result["queue_verify_without_sandbox_truth_count"] == 1
    assert result["sandbox_truth_without_queue_task_count"] == 1
    assert result["warnings"]


def test_generate_queue_sandbox_projection_report_writes_only_tmp_path(tmp_path, monkeypatch):
    output_path = tmp_path / "sample.json"
    monkeypatch.setattr(
        projection,
        "load_experiment_queue_snapshot",
        lambda queue_path=None: {"task_count": 0, "warnings": []},
    )
    monkeypatch.setattr(
        projection,
        "project_sandbox_outcomes",
        lambda limit=100: {"execution_truth_count": 0, "truth_events": [], "warnings": []},
    )
    monkeypatch.setattr(
        projection,
        "get_sandbox_execution_success_candidates",
        lambda limit=100: {"eligible_events": [], "warnings": []},
    )
    monkeypatch.setattr(
        projection,
        "correlate_queue_with_sandbox_truth",
        lambda queue_path=None, limit=100: {"warnings": []},
    )

    result = projection.generate_queue_sandbox_projection_report(str(output_path))

    assert result["written"] is True
    assert Path(result["output_path"]) == output_path
    assert output_path.exists()
