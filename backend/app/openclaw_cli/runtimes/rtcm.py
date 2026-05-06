"""RTCM runtime wrapper for OpenClaw operator CLI.

Dry-run only — delegates to execute_rtcm_dry_run without
reading .deerflow/rtcm operational data, token_cache.json, or making network calls.
"""

from __future__ import annotations

from app.rtcm import RoundtableRequest, execute_rtcm_dry_run

from ..commands import OperatorCommandResult


def run_rtcm_dry_run(
    *,
    topic: str = "OpenClaw operator dry-run roundtable",
) -> OperatorCommandResult:
    """Run an RTCM roundtable dry-run.

    Args:
        topic: Topic description for the roundtable.

    Returns:
        OperatorCommandResult with dry_run=True and DecisionRecord payload.
    """
    req = RoundtableRequest.new(
        topic=topic,
        reason="OpenClaw operator dry-run",
        dry_run=True,
    )

    record = execute_rtcm_dry_run(req)

    return OperatorCommandResult(
        command="rtcm-dry-run",
        status="success",
        dry_run=True,
        payload={
            "request_id": record.request.id if hasattr(record.request, "id") else None,
            "status": record.status,
            "topic": record.request.topic if hasattr(record.request, "topic") else topic,
            "member_count": len(record.members),
            "consensus": record.consensus.to_dict() if hasattr(record.consensus, "to_dict") else {},
            "decision": record.consensus.decision if hasattr(record.consensus, "decision") else "",
            "dry_run": record.consensus.dry_run if hasattr(record.consensus, "dry_run") else True,
        },
        warnings=[
            "Dry-run only — no real agents consulted",
            "No .deerflow/rtcm operational data read",
            "No Feishu/Lark real-send",
        ],
    )
