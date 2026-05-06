"""Consensus computation for RTCM roundtable runtime.

Deterministic majority-consensus — no external I/O.
"""

from __future__ import annotations

from collections import defaultdict

from .models import ConsensusResult, RoundtableRequest, Vote


def compute_majority_consensus(
    request: RoundtableRequest,
    votes: list[Vote],
) -> ConsensusResult:
    """Compute majority consensus from a list of votes.

    Aggregates votes by decision, weighted by each member's weight.
    The decision with the highest total weight wins.

    Args:
        request: The roundtable request (used for request_id).
        votes: List of votes from council members.

    Returns:
        ConsensusResult with the winning decision and confidence score.
    """
    if not votes:
        return ConsensusResult(
            request_id=request.id,
            strategy="majority_weighted",
            decision="no_votes",
            confidence=0.0,
            votes=[],
            dry_run=True,
            warnings=[
                "RTCM dry-run runtime does not read operational logs",
                "RTCM dry-run runtime does not send external messages",
            ],
        )

    # Aggregate weights by decision
    weight_by_decision: dict[str, float] = defaultdict(float)
    for v in votes:
        weight_by_decision[v.decision] += v.weight

    # Find winning decision
    winning_decision = max(weight_by_decision, key=weight_by_decision.__getitem__)
    winning_weight = weight_by_decision[winning_decision]
    total_weight = sum(v.weight for v in votes)
    confidence = winning_weight / total_weight if total_weight > 0 else 0.0

    return ConsensusResult(
        request_id=request.id,
        strategy="majority_weighted",
        decision=winning_decision,
        confidence=confidence,
        votes=votes,
        dry_run=True,
        warnings=[
            "RTCM dry-run runtime does not read operational logs",
            "RTCM dry-run runtime does not send external messages",
        ],
    )
