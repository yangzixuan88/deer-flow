"""OpenClaw operator dry-run CLI package.

Unified console for Nightly Review / Asset / RTCM dry-run runtimes.
Safe for operator use — no credentials, no network, no real send.
"""

from __future__ import annotations

from .commands import OperatorCommand, OperatorCommandResult, command_to_dict, list_commands
from .console import capability_summary, main, run_command
from .runtimes import (
    preview_nightly_schedule,
    run_asset_dry_run,
    run_nightly_dry_run,
    run_rtcm_dry_run,
)

__all__ = [
    "capability_summary",
    "command_to_dict",
    "list_commands",
    "main",
    "OperatorCommand",
    "OperatorCommandResult",
    "preview_nightly_schedule",
    "run_asset_dry_run",
    "run_command",
    "run_nightly_dry_run",
    "run_rtcm_dry_run",
]