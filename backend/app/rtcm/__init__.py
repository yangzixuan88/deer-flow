"""RTCM roundtable runtime adapter package.

Scope (R224):
- RoundtableRequest, CouncilMember, Vote, ConsensusResult, DecisionRecord models
- CouncilOrchestrator (build_default_council / build_council)
- VoteCollector (cast_dry_run_votes)
- ConsensusEngine (compute_majority_consensus)
- RTCMReporter (build_markdown_report / build_json_report)
- RTCMDecisionStore (JSONL persistence)
- Integration helpers (mode_decision_to_roundtable_request, execute_rtcm_dry_run)

Out of scope for R224:
- Real agent handoff
- Feishu/Lark real-send
- Agent-S runtime integration
- Scheduler daemon
"""

from __future__ import annotations

from .consensus import compute_majority_consensus
from .council import build_council, build_default_council
from .integration import execute_rtcm_dry_run, mode_decision_to_roundtable_request
from .models import (
    ConsensusResult,
    CouncilMember,
    DecisionRecord,
    RoundtableRequest,
    Vote,
)
from .reporter import build_decision_record, build_json_report, build_markdown_report
from .store import RTCMDecisionStore
from .vote import cast_dry_run_votes

__all__ = [
    "ConsensusResult",
    "CouncilMember",
    "DecisionRecord",
    "RTCMDecisionStore",
    "RoundtableRequest",
    "Vote",
    "build_council",
    "build_default_council",
    "build_decision_record",
    "build_json_report",
    "build_markdown_report",
    "cast_dry_run_votes",
    "compute_majority_consensus",
    "execute_rtcm_dry_run",
    "mode_decision_to_roundtable_request",
]
