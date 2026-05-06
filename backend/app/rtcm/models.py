"""RTCM runtime data models.

No external I/O, no network access, no credentials.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field


@dataclass
class CouncilMember:
    """A member of the roundtable council."""

    id: str
    name: str
    role: str = "member"
    weight: float = 1.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> CouncilMember:
        return cls(**d)


@dataclass
class RoundtableRequest:
    """A request for a roundtable / RTCM session."""

    id: str
    topic: str
    reason: str
    user_id: str | None
    thread_id: str | None
    run_id: str | None
    source: str = "mode_router"
    dry_run: bool = True

    @classmethod
    def new(
        cls,
        topic: str = "",
        reason: str = "",
        user_id: str | None = None,
        thread_id: str | None = None,
        run_id: str | None = None,
        source: str = "mode_router",
        dry_run: bool = True,
    ) -> RoundtableRequest:
        return cls(
            id=str(uuid.uuid4()),
            topic=topic,
            reason=reason,
            user_id=user_id,
            thread_id=thread_id,
            run_id=run_id,
            source=source,
            dry_run=dry_run,
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> RoundtableRequest:
        return cls(**d)


@dataclass
class Vote:
    """A single vote cast by a council member."""

    member_id: str
    decision: str
    rationale: str
    weight: float = 1.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Vote:
        return cls(**d)


@dataclass
class ConsensusResult:
    """Result of the consensus computation."""

    request_id: str
    strategy: str
    decision: str
    confidence: float
    votes: list[Vote] = field(default_factory=list)
    dry_run: bool = True
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> ConsensusResult:
        votes_data = d.pop("votes", [])
        warnings_data = d.pop("warnings", [])
        votes = [Vote.from_dict(v) for v in votes_data]
        instance = cls(**d)
        instance.votes = votes
        instance.warnings = warnings_data
        return instance


@dataclass
class DecisionRecord:
    """Complete record of a roundtable decision."""

    request: RoundtableRequest
    members: list[CouncilMember]
    consensus: ConsensusResult
    status: str = "dry_run"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> DecisionRecord:
        request = RoundtableRequest.from_dict(d.pop("request"))
        members_data = d.pop("members", [])
        members = [CouncilMember.from_dict(m) for m in members_data]
        consensus = ConsensusResult.from_dict(d.pop("consensus"))
        status = d.pop("status", "dry_run")
        instance = cls(request=request, members=members, consensus=consensus, status=status)
        return instance
