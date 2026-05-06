"""RTCM runtime wrapper for OpenClaw operator CLI.

Dry-run only — delegates to execute_rtcm_dry_run without
reading .deerflow/rtcm operational data, token_cache.json, or making network calls.
"""

from __future__ import annotations

from pathlib import Path

from app.rtcm import (
    RoundtableRequest,
    RTCMDecisionStore,
    build_json_index,
    build_markdown_report,
    execute_rtcm_dry_run,
)

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


def run_rtcm_dry_run_export(
    *,
    output: str | Path,
) -> OperatorCommandResult:
    """Run RTCM dry-run and export markdown report to an explicit path.

    Args:
        output: Explicit output path for the markdown report.
                Parent directories are created automatically.

    Returns:
        OperatorCommandResult with output_path, request_id, dry_run=True.
    """
    req = RoundtableRequest.new(
        topic="OpenClaw operator dry-run export",
        reason="OpenClaw operator dry-run export",
        dry_run=True,
    )

    record = execute_rtcm_dry_run(req)
    report = build_markdown_report(record)

    p = Path(output)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(report, encoding="utf-8")

    return OperatorCommandResult(
        command="rtcm-dry-run-export",
        status="success",
        dry_run=True,
        payload={
            "output_path": str(p.resolve()),
            "request_id": record.request.id if hasattr(record.request, "id") else None,
            "dry_run": True,
        },
        warnings=[
            "Dry-run only — no real agents consulted",
            "No .deerflow/rtcm operational data read",
        ],
    )


def run_rtcm_report_index(
    *,
    store: str | Path,
    limit: int | None = None,
) -> OperatorCommandResult:
    """Build a JSON index from an explicit RTCM store path.

    Args:
        store: Explicit path to the RTCMDecisionStore JSONL file.
        limit: Optional maximum number of records to include (most recent first).

    Returns:
        OperatorCommandResult with index dict, record count, dry_run=True.
    """
    store_obj = RTCMDecisionStore(store)
    records = store_obj.list_records(limit=limit)
    index = build_json_index(records)

    return OperatorCommandResult(
        command="rtcm-report-index",
        status="success",
        dry_run=True,
        payload={
            "store_path": str(Path(store).resolve()),
            "record_count": len(records),
            "index": index,
            "dry_run": True,
        },
        warnings=[
            "No .deerflow/rtcm operational data read",
            "No Feishu/Lark real-send",
        ],
    )
