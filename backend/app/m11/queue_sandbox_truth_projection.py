"""Read-only Queue / Sandbox truth projection diagnostics.

This module does not execute queue tasks, does not mutate experiment_queue.json,
and does not mutate governance_state.json. It only reads existing artifacts and
projects legacy sandbox outcomes through the R241 Truth/State wrappers.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.app.m11.governance_bridge import (
    get_success_rate_candidates,
    project_recent_outcomes,
    project_truth_state,
)


DEFAULT_EXPERIMENT_QUEUE_PATH = Path(
    r"C:\Users\win\.deerflow\upgrade-center\state\experiment_queue.json"
)
DEFAULT_RUNTIME_SAMPLE_PATH = Path(
    r"E:\OpenClaw-Base\deerflow\migration_reports\foundation_audit"
) / "R241-1C_QUEUE_SANDBOX_TRUTH_PROJECTION_RUNTIME_SAMPLE.json"


def load_experiment_queue_snapshot(queue_path: Optional[str] = None) -> Dict[str, Any]:
    """Read experiment_queue.json and return a diagnostic snapshot."""
    path = Path(queue_path) if queue_path else DEFAULT_EXPERIMENT_QUEUE_PATH
    result = {
        "queue_path": str(path),
        "exists": path.exists(),
        "task_count": 0,
        "status_counts": {},
        "with_verify_script_count": 0,
        "verify_script_basename_counts": {},
        "queue_tasks": [],
        "warnings": [],
    }
    if not path.exists():
        result["warnings"].append(f"queue_missing:{path}")
        return result

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        result["warnings"].append(f"queue_read_failed:{type(exc).__name__}:{exc}")
        return result

    tasks = _extract_queue_tasks(data)
    result["task_count"] = len(tasks)

    status_counts = Counter()
    verify_basename_counts = Counter()
    queue_tasks = []
    for task in tasks:
        status = str(task.get("status") or task.get("state") or "unknown")
        verify_path = task.get("verify_script_path") or task.get("verify_path")
        status_counts[status] += 1
        if verify_path:
            verify_basename_counts[Path(str(verify_path)).name] += 1
        queue_tasks.append(
            {
                "candidate_id": _first_present(task, "candidate_id", "candidateId"),
                "task_id": _first_present(task, "task_id", "taskId", "id"),
                "status": status,
                "verify_script_path": verify_path,
                "verify_script_basename": Path(str(verify_path)).name if verify_path else None,
            }
        )

    result["status_counts"] = dict(status_counts)
    result["with_verify_script_count"] = sum(1 for task in queue_tasks if task["verify_script_path"])
    result["verify_script_basename_counts"] = dict(verify_basename_counts)
    result["queue_tasks"] = queue_tasks
    return result


def project_sandbox_outcomes(limit: int = 100) -> Dict[str, Any]:
    """Project recent sandbox_execution_result outcomes into sandbox truth stats."""
    recent = project_recent_outcomes(limit=limit, outcome_type="sandbox_execution_result")
    records, read_warnings = _load_recent_sandbox_records(limit)

    truth_events: List[Dict[str, Any]] = []
    state_events: List[Dict[str, Any]] = []
    warnings = list(recent.get("warnings") or []) + read_warnings

    for record in records:
        projection = project_truth_state(record)
        truth_events.extend(projection.get("truth_events") or [])
        state_events.extend(projection.get("state_events") or [])
        warnings.extend(projection.get("warnings") or [])

    execution_actuals = [
        event for event in truth_events
        if event.get("truth_track") == "execution_truth"
        and event.get("truth_type") == "actual_outcome"
    ]
    predicted_events = [
        event for event in truth_events
        if event.get("truth_type") == "predicted_outcome"
        and event.get("predicted_value") is not None
    ]

    return {
        "sandbox_records_count": recent.get("total_scanned", len(records)),
        "truth_events_count": len(truth_events) if truth_events else recent.get("truth_events_count", 0),
        "state_events_count": len(state_events) if state_events else recent.get("state_events_count", 0),
        "execution_truth_count": len(execution_actuals),
        "actual_pass_count": sum(1 for event in execution_actuals if event.get("actual_value") == 1.0),
        "actual_fail_count": sum(1 for event in execution_actuals if event.get("actual_value") == 0.0),
        "predicted_present_count": len(predicted_events),
        "truth_events": truth_events,
        "state_events": state_events,
        "warnings": _dedupe(warnings),
    }


def get_sandbox_execution_success_candidates(limit: int = 100) -> Dict[str, Any]:
    """Return raw execution-truth candidates for sandbox success diagnostics."""
    candidates = get_success_rate_candidates("execution_success_rate", limit=limit)
    eligible_events = [
        event for event in candidates.get("eligible_events", [])
        if event.get("truth_track") == "execution_truth"
        and event.get("truth_type") in {"actual_outcome", "verification_result"}
    ]
    pass_count = sum(1 for event in eligible_events if event.get("actual_value") == 1.0)
    fail_count = sum(1 for event in eligible_events if event.get("actual_value") == 0.0)
    denominator = pass_count + fail_count

    return {
        "metric_scope": "execution_success_rate",
        "eligible_count": len(eligible_events),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "simple_success_rate": (pass_count / denominator) if denominator else None,
        "rate_note": "raw execution truth rate; not a user-goal success rate",
        "eligible_events": eligible_events,
        "excluded_reasons": candidates.get("excluded_reasons", {}),
        "warnings": candidates.get("warnings", []),
    }


def correlate_queue_with_sandbox_truth(
    queue_path: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """Read-only queue snapshot to sandbox truth diagnostic correlation."""
    queue_snapshot = load_experiment_queue_snapshot(queue_path)
    sandbox_projection = project_sandbox_outcomes(limit=limit)

    queue_keys = _queue_keys(queue_snapshot.get("queue_tasks") or [])
    truth_items = _truth_items(sandbox_projection.get("truth_events") or [])
    truth_keys = {key for item in truth_items for key in item["keys"]}

    queue_with_verify_without_truth = 0
    for task in queue_snapshot.get("queue_tasks") or []:
        task_keys = _keys_for_queue_task(task)
        if task.get("verify_script_path") and not task_keys.intersection(truth_keys):
            queue_with_verify_without_truth += 1

    truth_without_queue = 0
    truth_predicted_present = 0
    truth_with_provenance = 0
    for item in truth_items:
        if item["predicted_present"]:
            truth_predicted_present += 1
        if item["keys"]:
            truth_with_provenance += 1
        if not item["keys"].intersection(queue_keys):
            truth_without_queue += 1

    warnings = list(queue_snapshot.get("warnings") or []) + list(sandbox_projection.get("warnings") or [])
    if queue_with_verify_without_truth:
        warnings.append(f"queue_verify_without_sandbox_truth:{queue_with_verify_without_truth}")
    if truth_without_queue:
        warnings.append(f"sandbox_truth_without_queue_task:{truth_without_queue}")

    return {
        "queue_status_counts": queue_snapshot.get("status_counts", {}),
        "queue_task_count": queue_snapshot.get("task_count", 0),
        "sandbox_truth_count": sandbox_projection.get("execution_truth_count", 0),
        "sandbox_predicted_present_count": truth_predicted_present,
        "sandbox_truth_with_provenance_count": truth_with_provenance,
        "queue_verify_without_sandbox_truth_count": queue_with_verify_without_truth,
        "sandbox_truth_without_queue_task_count": truth_without_queue,
        "warnings": _dedupe(warnings),
    }


def generate_queue_sandbox_projection_report(output_path: Optional[str] = None) -> Dict[str, Any]:
    """Generate an audit-only JSON report under migration_reports by default."""
    target = Path(output_path) if output_path else DEFAULT_RUNTIME_SAMPLE_PATH
    queue_snapshot = load_experiment_queue_snapshot()
    sandbox_projection = project_sandbox_outcomes()
    execution_success_candidates = get_sandbox_execution_success_candidates()
    queue_truth_correlation = correlate_queue_with_sandbox_truth()
    warnings = _dedupe(
        list(queue_snapshot.get("warnings") or [])
        + list(sandbox_projection.get("warnings") or [])
        + list(execution_success_candidates.get("warnings") or [])
        + list(queue_truth_correlation.get("warnings") or [])
    )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "queue_snapshot": queue_snapshot,
        "sandbox_projection": _without_large_events(sandbox_projection),
        "execution_success_candidates": _without_large_events(execution_success_candidates),
        "queue_truth_correlation": queue_truth_correlation,
        "warnings": warnings,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "output_path": str(target),
        "written": True,
        "warnings": warnings,
        "generated_at": report["generated_at"],
    }


def _load_recent_sandbox_records(limit: int) -> Tuple[List[Dict[str, Any]], List[str]]:
    try:
        from backend.app.m11 import governance_bridge

        records, warnings = governance_bridge._read_outcome_records_readonly()
    except Exception as exc:
        return [], [f"governance_read_failed:{type(exc).__name__}:{exc}"]
    sandbox_records = [
        record for record in records
        if record.get("outcome_type") == "sandbox_execution_result"
    ]
    return sandbox_records[-_clamp(limit):], warnings


def _extract_queue_tasks(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        return []
    for key in ("tasks", "queue", "items", "experiments", "pending", "running", "completed"):
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    task = data.get("task")
    if isinstance(task, dict):
        return [task]
    return []


def _queue_keys(tasks: List[Dict[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for task in tasks:
        keys.update(_keys_for_queue_task(task))
    return keys


def _keys_for_queue_task(task: Dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for key in ("candidate_id", "task_id"):
        if task.get(key):
            keys.add(f"{key}:{task[key]}")
    if task.get("verify_script_basename"):
        keys.add(f"verify_script_basename:{task['verify_script_basename']}")
    return keys


def _truth_items(truth_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    predicted_keys: set[str] = set()
    for event in truth_events:
        if (
            event.get("truth_track") == "execution_truth"
            and event.get("truth_type") == "predicted_outcome"
        ):
            predicted_keys.update(_keys_for_truth_event(event))

    for event in truth_events:
        if event.get("truth_track") != "execution_truth":
            continue
        if event.get("truth_type") not in {"actual_outcome", "verification_result"}:
            continue
        keys = _keys_for_truth_event(event)
        items.append(
            {
                "keys": keys,
                "predicted_present": event.get("predicted_value") is not None
                or bool(keys.intersection(predicted_keys)),
            }
        )
    return items


def _keys_for_truth_event(event: Dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    subject_id = event.get("subject_id")
    if subject_id and subject_id != "unknown":
        keys.add(f"candidate_id:{subject_id}")
        keys.add(f"task_id:{subject_id}")
    for ref in event.get("evidence_refs") or []:
        key = ref.get("key")
        value = ref.get("value")
        if value is None:
            continue
        if key in {"candidate_id", "task_id"}:
            keys.add(f"{key}:{value}")
        if key in {"verify_script_path", "execution_result_path"}:
            keys.add(f"verify_script_basename:{Path(str(value)).name}")
    return keys


def _without_large_events(data: Dict[str, Any]) -> Dict[str, Any]:
    compact = dict(data)
    for key in ("truth_events", "state_events", "eligible_events"):
        if key in compact:
            compact[f"{key}_count"] = len(compact.get(key) or [])
            compact.pop(key, None)
    return compact


def _first_present(mapping: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if mapping.get(key) is not None:
            return mapping.get(key)
    return None


def _clamp(limit: int) -> int:
    try:
        parsed = int(limit)
    except (TypeError, ValueError):
        parsed = 100
    return max(0, min(parsed, 200))


def _dedupe(items: List[str]) -> List[str]:
    return list(dict.fromkeys(str(item) for item in items))
