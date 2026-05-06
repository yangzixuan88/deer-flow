"""Integration helpers for RTCM runtime.

Bridges mode_router decisions to the RTCM roundtable runtime.
Never modifies mode_router.py. Never accesses operational data.
"""

from __future__ import annotations

from .consensus import compute_majority_consensus
from .council import build_default_council
from .models import DecisionRecord, RoundtableRequest
from .reporter import build_decision_record
from .vote import cast_dry_run_votes


def mode_decision_to_roundtable_request(
    mode_result,
    *,
    user_id: str | None = None,
    thread_id: str | None = None,
    run_id: str | None = None,
    reason: str | None = None,
    topic: str = "OpenClaw roundtable dry-run review",
    source: str = "mode_router",
) -> RoundtableRequest | None:
    """Convert a mode router decision into a RoundtableRequest.

    Checks the mode_result for ROUNDTABLE mode or RTCM_MAIN_AGENT_HANDOFF
    delegation marker. Returns None if the mode does not indicate a
    roundtable session.

    Supports both object-like (mode_result.selected_mode) and
    dict-like (mode_result["selected_mode"]) access.

    Args:
        mode_result: Mode router decision result.
        user_id: Optional user identifier.
        thread_id: Optional thread identifier.
        run_id: Optional run identifier.
        reason: Optional reason override. If None, extracted from mode_result.
        topic: Default topic for the roundtable.
        source: Source identifier (default: mode_router).

    Returns:
        RoundtableRequest if mode indicates roundtable, None otherwise.
    """
    # Extract selected_mode using both attribute and dict access
    selected_mode: str | None = None
    if hasattr(mode_result, "selected_mode"):
        selected_mode = mode_result.selected_mode
    elif isinstance(mode_result, dict) and "selected_mode" in mode_result:
        selected_mode = mode_result.get("selected_mode")

    # Extract delegated_to using both attribute and dict access
    delegated_to: str | None = None
    if hasattr(mode_result, "delegated_to"):
        delegated_to = mode_result.delegated_to
    elif isinstance(mode_result, dict) and "delegated_to" in mode_result:
        delegated_to = mode_result.get("delegated_to")

    # Check for roundtable routing
    is_roundtable = selected_mode == "ROUNDTABLE" or (delegated_to is not None and "RTCM_MAIN_AGENT_HANDOFF" in str(delegated_to))

    if not is_roundtable:
        return None

    # Extract reason
    if reason is None:
        if hasattr(mode_result, "reason"):
            reason = str(mode_result.reason)
        elif isinstance(mode_result, dict):
            reason = str(mode_result.get("reason", "mode router roundtable handoff"))
        else:
            reason = "mode router roundtable handoff"

    return RoundtableRequest.new(
        topic=topic,
        reason=reason,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        source=source,
        dry_run=True,
    )


def execute_rtcm_dry_run(request: RoundtableRequest) -> DecisionRecord:
    """Execute a full RTCM dry-run roundtrip for the given request.

    Orchestrates: build_default_council -> cast_dry_run_votes ->
    compute_majority_consensus -> build_decision_record.

    Does NOT write to store, send messages, or access the network.

    Args:
        request: The RoundtableRequest to process.

    Returns:
        DecisionRecord with the complete roundtable outcome.
    """
    members = build_default_council()
    votes = cast_dry_run_votes(request, members)
    consensus = compute_majority_consensus(request, votes)
    record = build_decision_record(request, members, votes, consensus)
    return record
