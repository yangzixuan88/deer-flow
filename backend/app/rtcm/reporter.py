"""Report builders for RTCM roundtable decisions.

No Feishu/Lark send, no credential access, no network calls.
"""

from __future__ import annotations

from .models import (
    ConsensusResult,
    CouncilMember,
    DecisionRecord,
    RoundtableRequest,
    Vote,
)


def build_decision_record(
    request: RoundtableRequest,
    members: list[CouncilMember],
    votes: list[Vote],
    consensus: ConsensusResult,
) -> DecisionRecord:
    """Assemble a complete DecisionRecord from the given components.

    Args:
        request: The roundtable request.
        members: Council members who participated.
        votes: Votes cast by the council.
        consensus: Computed consensus result.

    Returns:
        DecisionRecord with all fields populated.
    """
    return DecisionRecord(
        request=request,
        members=members,
        consensus=consensus,
        status="dry_run",
    )


def build_markdown_report(record: DecisionRecord) -> str:
    """Build a Markdown-formatted report from a DecisionRecord.

    Args:
        record: The decision record to format.

    Returns:
        Markdown string.
    """
    lines = [
        "# RTCM Roundtable Decision Report",
        "",
        f"**Status**: {record.status}",
        f"**Topic**: {record.request.topic}",
        f"**Reason**: {record.request.reason}",
        "",
        "## Council Members",
    ]
    for m in record.members:
        lines.append(f"- `{m.id}` — {m.name} ({m.role}, weight={m.weight})")

    lines.extend(["", "## Consensus", f"- **Decision**: {record.consensus.decision}"])
    if record.consensus.warnings:
        lines.append("- **Warnings**:")
        for w in record.consensus.warnings:
            lines.append(f"  - {w}")

    lines.extend(
        [
            f"- **Confidence**: {record.consensus.confidence:.2%}",
            f"- **Strategy**: {record.consensus.strategy}",
            "",
            "## Votes",
        ]
    )
    for v in record.consensus.votes:
        lines.append(f"- `{v.member_id}` → **{v.decision}** (weight={v.weight})")
        lines.append(f"  - {v.rationale}")

    return "\n".join(lines)


def build_json_report(record: DecisionRecord) -> dict:
    """Build a JSON-serializable dict from a DecisionRecord.

    Args:
        record: The decision record to serialize.

    Returns:
        Dictionary representation.
    """
    return record.to_dict()


def build_markdown_index(records: list[DecisionRecord]) -> str:
    """Build a merged Markdown report from multiple DecisionRecords.

    Args:
        records: List of decision records to include.

    Returns:
        Merged markdown string.
    """
    if not records:
        return "# RTCM Roundtable Decision Index\n\n*No records.*\n"

    lines = [
        "# RTCM Roundtable Decision Index",
        "",
        f"**Count**: {len(records)}",
        "**Status**: dry-run",
        "",
    ]
    for i, record in enumerate(records, 1):
        lines.append(f"## {i}. {record.request.topic}")
        lines.append(f"- **Request ID**: `{record.request.id}`")
        lines.append(f"- **Status**: {record.status}")
        lines.append(f"- **Decision**: {record.consensus.decision}")
        lines.append(f"- **Confidence**: {record.consensus.confidence:.2%}")
        lines.append(f"- **Members**: {len(record.members)}")
        lines.append("")
    return "\n".join(lines)


def build_json_index(records: list[DecisionRecord]) -> dict:
    """Build a JSON-serializable index from multiple DecisionRecords.

    Args:
        records: List of decision records to index.

    Returns:
        Dictionary with count, request_ids, statuses, and records.
    """
    return {
        "count": len(records),
        "request_ids": [getattr(r.request, "id", None) for r in records],
        "statuses": [r.status for r in records],
        "dry_run": all(getattr(r.consensus, "dry_run", True) for r in records),
        "records": [r.to_dict() for r in records],
    }
