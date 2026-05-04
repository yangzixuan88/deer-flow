"""Read-only Truth / State projection helpers for legacy governance outcomes.

This module does not mutate governance_state.json and does not change legacy
record_outcome() write semantics. It only projects existing records into typed
TruthEvent / StateEvent dictionaries for downstream reporting and wrappers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


TRUTH_TYPES = {
    "predicted_outcome",
    "actual_outcome",
    "observation_signal",
    "approval_decision",
    "execution_result",
    "verification_result",
    "rollback_result",
    "asset_quality_signal",
    "memory_update_signal",
    "prompt_optimization_signal",
    "rtcm_verdict",
    "tool_execution_result",
}

TRUTH_TRACKS = {
    "execution_truth",
    "governance_truth",
    "observation_truth",
    "user_truth",
    "asset_truth",
    "memory_truth",
    "prompt_truth",
    "rtcm_truth",
    "tool_truth",
}

STATE_DOMAINS = {
    "gateway_run",
    "deerflow_thread",
    "m01_request",
    "m04_task",
    "m04_workflow",
    "rtcm_session",
    "governance_decision",
    "experiment_queue_task",
    "sandbox_execution",
    "asset_lifecycle",
    "memory_update",
    "prompt_optimization",
    "nightly_review",
    "mode_invocation",
    "tool_execution",
}


@dataclass(frozen=True)
class TruthEvent:
    truth_event_id: str
    source_system: str
    truth_type: str
    truth_track: str
    subject_type: str
    subject_id: str
    predicted_value: Optional[Any]
    actual_value: Optional[Any]
    confidence: Optional[float]
    evidence_refs: List[Dict[str, Any]]
    producer: str
    created_at: str
    context_id: Optional[str] = None
    request_id: Optional[str] = None
    governance_trace_id: Optional[str] = None
    related_state_id: Optional[str] = None
    legacy_outcome_type: Optional[str] = None
    legacy_record_ref: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class StateEvent:
    state_event_id: str
    source_system: str
    state_domain: str
    subject_type: str
    subject_id: str
    previous_state: Optional[str]
    new_state: str
    transition_reason: Optional[str]
    actor_system: str
    created_at: str
    context_id: Optional[str] = None
    request_id: Optional[str] = None
    related_truth_event_id: Optional[str] = None
    artifact_refs: List[Dict[str, Any]] = field(default_factory=list)
    legacy_outcome_type: Optional[str] = None
    legacy_record_ref: Optional[Dict[str, Any]] = None


def map_legacy_outcome_to_truth_events(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Project one legacy outcome record into zero or more TruthEvent dicts."""
    outcome_type = str(record.get("outcome_type") or "")
    context = _context(record)

    if not outcome_type:
        return []

    events: List[Dict[str, Any]] = []

    if outcome_type == "sandbox_execution_result":
        if _is_binary_outcome(record.get("actual")):
            events.append(
                _truth_event(
                    record,
                    truth_type="actual_outcome",
                    truth_track="execution_truth",
                    subject_type="sandbox_execution",
                    actual_value=record.get("actual"),
                    predicted_value=record.get("predicted"),
                    evidence_refs=_evidence_refs(
                        record,
                        keys=("verify_exit_code", "rollback_invoked", "execution_result_path"),
                    ),
                )
            )
        if record.get("predicted") is not None:
            events.append(
                _truth_event(
                    record,
                    truth_type="predicted_outcome",
                    truth_track="execution_truth",
                    subject_type="sandbox_execution",
                    predicted_value=record.get("predicted"),
                    evidence_refs=_evidence_refs(record, keys=("predicted", "candidate_id")),
                )
            )
        return events

    if outcome_type == "upgrade_center_execution_result":
        filter_result = context.get("filter_result") or context.get("execution_stage")
        actual = record.get("actual")

        if record.get("predicted") is not None:
            events.append(
                _truth_event(
                    record,
                    truth_type="predicted_outcome",
                    truth_track="governance_truth",
                    subject_type="upgrade_candidate",
                    predicted_value=record.get("predicted"),
                    evidence_refs=_evidence_refs(record, keys=("predicted", "candidate_id", "tier")),
                )
            )

        if filter_result == "observation_pool" and actual == 0.5:
            events.append(
                _truth_event(
                    record,
                    truth_type="observation_signal",
                    truth_track="observation_truth",
                    subject_type="upgrade_candidate",
                    actual_value=actual,
                    predicted_value=record.get("predicted"),
                    evidence_refs=_evidence_refs(
                        record,
                        keys=("filter_result", "execution_stage", "candidate_id", "tier"),
                    ),
                )
            )
        elif actual == 1.0:
            events.append(
                _truth_event(
                    record,
                    truth_type="approval_decision",
                    truth_track="governance_truth",
                    subject_type="upgrade_candidate",
                    actual_value=actual,
                    predicted_value=record.get("predicted"),
                    evidence_refs=_evidence_refs(
                        record,
                        keys=("filter_result", "execution_stage", "candidate_id", "requires_approval"),
                    ),
                )
            )
        return events

    if outcome_type == "upgrade_center_approval":
        events.append(
            _truth_event(
                record,
                truth_type="approval_decision",
                truth_track="governance_truth",
                subject_type="upgrade_candidate",
                actual_value=record.get("actual"),
                predicted_value=record.get("predicted"),
                evidence_refs=_evidence_refs(
                    record,
                    keys=("candidate_id", "requires_approval", "can_proceed_to_experiment"),
                ),
            )
        )
        if record.get("predicted") is not None:
            events.append(
                _truth_event(
                    record,
                    truth_type="predicted_outcome",
                    truth_track="governance_truth",
                    subject_type="upgrade_candidate",
                    predicted_value=record.get("predicted"),
                    evidence_refs=_evidence_refs(record, keys=("predicted", "candidate_id")),
                )
            )
        return events

    if outcome_type == "asset_promotion":
        score = _first_present(context, "score", "quality_score", "asset_score", "actual")
        if score is None:
            score = record.get("actual")
        events.append(
            _truth_event(
                record,
                truth_type="asset_quality_signal",
                truth_track="asset_truth",
                subject_type="asset",
                actual_value=score,
                predicted_value=record.get("predicted"),
                evidence_refs=_evidence_refs(
                    record,
                    keys=("asset_id", "candidate_id", "score", "quality_score", "tier"),
                ),
            )
        )
        return events

    if _is_rtcm_outcome(outcome_type, context):
        events.append(
            _truth_event(
                record,
                truth_type="rtcm_verdict",
                truth_track="rtcm_truth",
                subject_type="rtcm_session",
                actual_value=_first_present(
                    context,
                    "verdict",
                    "signoff",
                    "final_report",
                    "decision",
                    "actual",
                )
                or record.get("actual"),
                predicted_value=record.get("predicted"),
                evidence_refs=_evidence_refs(
                    record,
                    keys=("rtcm_session_id", "session_id", "verdict", "signoff", "final_report"),
                ),
            )
        )
        return events

    return []


def map_legacy_outcome_to_state_events(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Project one legacy outcome record into zero or more StateEvent dicts."""
    outcome_type = str(record.get("outcome_type") or "")
    context = _context(record)

    if not outcome_type:
        return []

    if outcome_type == "upgrade_queue_snapshot":
        tasks = _extract_tasks(context)
        if not tasks:
            tasks = [context]
        return [
            _state_event(
                record,
                state_domain="experiment_queue_task",
                subject_type="experiment_queue_task",
                subject_id=str(
                    task.get("candidate_id")
                    or task.get("task_id")
                    or task.get("id")
                    or _subject_id(record)
                ),
                previous_state=task.get("previous_status") or task.get("previous_state"),
                new_state=str(task.get("status") or context.get("status") or "snapshot"),
                transition_reason="legacy upgrade_queue_snapshot projection",
                artifact_refs=_artifact_refs(record, task),
            )
            for task in tasks
        ]

    if outcome_type == "sandbox_execution_result":
        verify_exit_code = _first_present(context, "verify_exit_code", "exit_code")
        if verify_exit_code is None:
            verify_exit_code = record.get("verify_exit_code")
        new_state = "completed" if verify_exit_code == 0 else "failed"
        transition_reason = "verify_exit_code=0" if verify_exit_code == 0 else "verify_exit_code_nonzero"
        if context.get("rollback_invoked"):
            transition_reason += "; rollback_invoked"
        return [
            _state_event(
                record,
                state_domain="sandbox_execution",
                subject_type="sandbox_execution",
                subject_id=_subject_id(record),
                previous_state=context.get("previous_state"),
                new_state=new_state,
                transition_reason=transition_reason,
                artifact_refs=_artifact_refs(record, context),
            )
        ]

    if outcome_type == "asset_promotion":
        promoted = bool(
            context.get("promoted")
            or context.get("promotion_applied")
            or context.get("bound")
            or record.get("actual") == 1.0
        )
        return [
            _state_event(
                record,
                state_domain="asset_lifecycle",
                subject_type="asset",
                subject_id=_subject_id(record),
                previous_state=context.get("previous_state") or context.get("from_tier"),
                new_state="promoted" if promoted else "candidate",
                transition_reason="legacy asset_promotion projection",
                artifact_refs=_artifact_refs(record, context),
            )
        ]

    if _is_rtcm_outcome(outcome_type, context):
        return [
            _state_event(
                record,
                state_domain="rtcm_session",
                subject_type="rtcm_session",
                subject_id=_subject_id(record),
                previous_state=context.get("previous_state"),
                new_state=str(
                    context.get("status")
                    or context.get("state")
                    or context.get("verdict")
                    or "verdict_recorded"
                ),
                transition_reason="legacy rtcm outcome projection",
                artifact_refs=_artifact_refs(record, context),
            )
        ]

    return []


def is_success_rate_eligible(truth_event: Dict[str, Any], metric_scope: str) -> bool:
    """Return whether a TruthEvent is eligible for a given success/quality metric."""
    truth_track = truth_event.get("truth_track")
    truth_type = truth_event.get("truth_type")

    if metric_scope == "execution_success_rate":
        return truth_track == "execution_truth" and truth_type in {
            "actual_outcome",
            "verification_result",
        }

    if metric_scope == "tool_success_rate":
        return truth_track == "tool_truth" and truth_type == "tool_execution_result"

    if metric_scope == "asset_quality_score":
        return truth_track == "asset_truth" and truth_type == "asset_quality_signal"

    if metric_scope == "rtcm_decision_quality":
        return truth_track == "rtcm_truth" and truth_type == "rtcm_verdict"

    return False


def summarize_outcome_contract(record: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize read-only contract projection for reporting/tests."""
    truth_events = map_legacy_outcome_to_truth_events(record)
    state_events = map_legacy_outcome_to_state_events(record)
    warnings = _warnings_for(record, truth_events, state_events)
    scopes = [
        scope
        for scope in (
            "execution_success_rate",
            "tool_success_rate",
            "asset_quality_score",
            "rtcm_decision_quality",
        )
        if any(is_success_rate_eligible(event, scope) for event in truth_events)
    ]
    return {
        "legacy_outcome_type": record.get("outcome_type"),
        "truth_events_count": len(truth_events),
        "state_events_count": len(state_events),
        "success_rate_eligible_scopes": scopes,
        "warnings": warnings,
        "semantic_classification": _semantic_classification(record, truth_events, state_events),
    }


def _truth_event(
    record: Dict[str, Any],
    *,
    truth_type: str,
    truth_track: str,
    subject_type: str,
    evidence_refs: Optional[List[Dict[str, Any]]] = None,
    predicted_value: Any = None,
    actual_value: Any = None,
) -> Dict[str, Any]:
    if truth_type not in TRUTH_TYPES:
        raise ValueError(f"Unsupported truth_type: {truth_type}")
    if truth_track not in TRUTH_TRACKS:
        raise ValueError(f"Unsupported truth_track: {truth_track}")

    event = TruthEvent(
        truth_event_id=f"truth_{uuid4().hex}",
        source_system=_source_system(record),
        truth_type=truth_type,
        truth_track=truth_track,
        subject_type=subject_type,
        subject_id=_subject_id(record),
        predicted_value=predicted_value,
        actual_value=actual_value,
        confidence=_confidence(record, truth_type),
        evidence_refs=evidence_refs or [],
        producer="truth_state_contract.map_legacy_outcome_to_truth_events",
        created_at=_created_at(record),
        context_id=_field(record, "context_id"),
        request_id=_field(record, "request_id"),
        governance_trace_id=_field(record, "governance_trace_id"),
        legacy_outcome_type=record.get("outcome_type"),
        legacy_record_ref=_legacy_record_ref(record),
    )
    return asdict(event)


def _state_event(
    record: Dict[str, Any],
    *,
    state_domain: str,
    subject_type: str,
    subject_id: str,
    previous_state: Optional[str],
    new_state: str,
    transition_reason: Optional[str],
    artifact_refs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if state_domain not in STATE_DOMAINS:
        raise ValueError(f"Unsupported state_domain: {state_domain}")

    event = StateEvent(
        state_event_id=f"state_{uuid4().hex}",
        source_system=_source_system(record),
        state_domain=state_domain,
        subject_type=subject_type,
        subject_id=subject_id,
        previous_state=previous_state,
        new_state=new_state,
        transition_reason=transition_reason,
        actor_system=_source_system(record),
        created_at=_created_at(record),
        context_id=_field(record, "context_id"),
        request_id=_field(record, "request_id"),
        artifact_refs=artifact_refs or [],
        legacy_outcome_type=record.get("outcome_type"),
        legacy_record_ref=_legacy_record_ref(record),
    )
    return asdict(event)


def _context(record: Dict[str, Any]) -> Dict[str, Any]:
    context = record.get("context")
    return context if isinstance(context, dict) else {}


def _field(record: Dict[str, Any], name: str) -> Optional[Any]:
    context = _context(record)
    return record.get(name) or context.get(name)


def _subject_id(record: Dict[str, Any]) -> str:
    context = _context(record)
    for key in (
        "candidate_id",
        "asset_id",
        "task_id",
        "execution_id",
        "rtcm_session_id",
        "session_id",
        "thread_id",
        "context_id",
        "governance_trace_id",
    ):
        value = record.get(key) or context.get(key)
        if value is not None:
            return str(value)
    return "unknown"


def _source_system(record: Dict[str, Any]) -> str:
    context = _context(record)
    outcome_type = str(record.get("outcome_type") or "")
    if context.get("source"):
        return str(context["source"])
    if outcome_type.startswith("upgrade_center_"):
        return "upgrade_center"
    if outcome_type.startswith("sandbox_"):
        return "sandbox_executor"
    if outcome_type.startswith("asset_"):
        return "asset_system"
    if _is_rtcm_outcome(outcome_type, context):
        return "rtcm"
    return "governance_bridge"


def _created_at(record: Dict[str, Any]) -> str:
    timestamp = record.get("timestamp") or record.get("created_at")
    if timestamp:
        return str(timestamp)
    return datetime.now(timezone.utc).isoformat()


def _confidence(record: Dict[str, Any], truth_type: str) -> Optional[float]:
    context = _context(record)
    raw = _first_present(context, "confidence", "quality_score", "score")
    if raw is None and truth_type in {"actual_outcome", "approval_decision"}:
        raw = record.get("actual")
    try:
        if raw is None:
            return None
        return float(raw)
    except (TypeError, ValueError):
        return None


def _legacy_record_ref(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "outcome_type": record.get("outcome_type"),
        "timestamp": record.get("timestamp"),
        "subject_id": _subject_id(record),
    }


def _evidence_refs(record: Dict[str, Any], *, keys: tuple[str, ...]) -> List[Dict[str, Any]]:
    context = _context(record)
    refs: List[Dict[str, Any]] = []
    for key in keys:
        if key in record:
            refs.append({"key": key, "value": record.get(key), "source": "record"})
        elif key in context:
            refs.append({"key": key, "value": context.get(key), "source": "context"})
    return refs


def _artifact_refs(record: Dict[str, Any], source: Dict[str, Any]) -> List[Dict[str, Any]]:
    refs: List[Dict[str, Any]] = []
    for key in (
        "report_path",
        "result_path",
        "execution_result_path",
        "rollback_path",
        "binding_report",
        "final_report",
    ):
        if source.get(key) is not None:
            refs.append({"key": key, "value": source.get(key)})
    rollback_invoked = _context(record).get("rollback_invoked")
    if rollback_invoked is not None:
        refs.append({"key": "rollback_invoked", "value": rollback_invoked})
    return refs


def _extract_tasks(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ("tasks", "queue", "items", "pending", "running", "completed"):
        value = context.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    task = context.get("task")
    if isinstance(task, dict):
        return [task]
    return []


def _warnings_for(
    record: Dict[str, Any],
    truth_events: List[Dict[str, Any]],
    state_events: List[Dict[str, Any]],
) -> List[str]:
    warnings: List[str] = []
    outcome_type = record.get("outcome_type")
    if not truth_events and not state_events:
        warnings.append(f"unknown_mapping:{outcome_type}")
    for event in truth_events:
        if event["truth_type"] in {"observation_signal", "approval_decision"}:
            warnings.append(f"not_execution_success_rate:{event['truth_type']}")
        if event["truth_type"] == "asset_quality_signal":
            warnings.append("asset_quality_signal_not_execution_truth")
    return warnings


def _semantic_classification(
    record: Dict[str, Any],
    truth_events: List[Dict[str, Any]],
    state_events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "has_execution_truth": any(e["truth_track"] == "execution_truth" for e in truth_events),
        "has_governance_truth": any(e["truth_track"] == "governance_truth" for e in truth_events),
        "has_observation_signal": any(e["truth_type"] == "observation_signal" for e in truth_events),
        "has_asset_quality_signal": any(e["truth_type"] == "asset_quality_signal" for e in truth_events),
        "has_rtcm_truth": any(e["truth_track"] == "rtcm_truth" for e in truth_events),
        "has_state_projection": bool(state_events),
    }


def _is_binary_outcome(value: Any) -> bool:
    return value in (0, 0.0, 1, 1.0)


def _is_rtcm_outcome(outcome_type: str, context: Dict[str, Any]) -> bool:
    lowered = outcome_type.lower()
    if "rtcm" in lowered or "roundtable" in lowered:
        return True
    return any(key in context for key in ("final_report", "signoff", "verdict", "rtcm_session_id"))


def _first_present(mapping: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None
