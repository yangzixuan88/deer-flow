"""Voting logic for RTCM roundtable runtime.

Deterministic dry-run voting — no model calls, no network access.
"""

from __future__ import annotations

from .council import build_council
from .models import CouncilMember, RoundtableRequest, Vote


def cast_dry_run_votes(
    request: RoundtableRequest,
    members: list[CouncilMember] | None = None,
) -> list[Vote]:
    """Cast deterministic dry-run votes for each council member.

    Each member votes "approve_dry_run" with a rationale noting this is
    a dry-run with no external agent invocation.

    Args:
        request: The roundtable request.
        members: Council members. If None, uses the default council.

    Returns:
        List of Vote objects, one per member.
    """
    council = build_council(members)
    rationale = f"Dry-run vote for topic '{request.topic}': approve for RTCM dry-run review. No external agents or real send triggered."
    return [
        Vote(
            member_id=m.id,
            decision="approve_dry_run",
            rationale=rationale,
            weight=m.weight,
        )
        for m in council
    ]
