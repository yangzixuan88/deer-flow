"""Council builder for RTCM roundtable runtime."""

from __future__ import annotations

from .models import CouncilMember

# Default council members for dry-run mode
_DEFAULT_MEMBERS: list[CouncilMember] = [
    CouncilMember(id="architect", name="Architect", role="architect", weight=1.0),
    CouncilMember(id="safety_reviewer", name="Safety Reviewer", role="safety_reviewer", weight=1.0),
    CouncilMember(
        id="implementation_reviewer",
        name="Implementation Reviewer",
        role="implementation_reviewer",
        weight=1.0,
    ),
]


def build_default_council() -> list[CouncilMember]:
    """Return the default dry-run council members."""
    return list(_DEFAULT_MEMBERS)


def build_council(members: list[CouncilMember] | None = None) -> list[CouncilMember]:
    """Build a council from explicit input, or return the default council.

    Args:
        members: Explicit list of council members. If None, returns the default council.

    Returns:
        List of council members.
    """
    if members is None:
        return build_default_council()
    return list(members)
