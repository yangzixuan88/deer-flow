"""Integration helpers for asset runtime.

Provides bridges between mode_router decisions and the asset runtime.
These helpers never modify mode_router.py — they consume its output types.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .dry_run import execute_asset_dry_run as _execute_asset_dry_run
from .models import AssetRequest

if TYPE_CHECKING:
    from .models import AssetResult


def mode_decision_to_asset_request(
    mode: str,
    reason: str,
    user_id: str | None = None,
    thread_id: str | None = None,
    run_id: str | None = None,
    requested_capability: str | None = None,
    payload_summary: str = "",
    source: str = "mode_router",
    dry_run: bool = True,
) -> AssetRequest:
    """Convert a mode decision into an AssetRequest.

    This helper is the integration point from mode_router into the asset runtime.
    It never reads from mode_router.py or modifies it.

    Args:
        mode: The routing mode (e.g. 'asset', 'delegated').
        reason: Human-readable reason for the mode selection.
        user_id: Optional user identifier.
        thread_id: Optional thread identifier.
        run_id: Optional run identifier.
        requested_capability: Optional specific capability requested.
        payload_summary: Summary of the payload being processed.
        source: Source of the request (default: 'mode_router').
        dry_run: Whether to run in dry-run mode (default: True).

    Returns:
        AssetRequest ready for execution.
    """
    return AssetRequest.new(
        mode=mode,
        reason=reason,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        requested_capability=requested_capability,
        payload_summary=payload_summary,
        source=source,
        dry_run=dry_run,
    )


def execute_asset_dry_run(request: AssetRequest) -> AssetResult:
    """Alias for execute_asset_dry_run from dry_run module.

    Provided here for consumers who import from integration.py.
    """
    return _execute_asset_dry_run(request)
