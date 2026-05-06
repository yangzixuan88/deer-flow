"""Dry-run execution helpers for asset runtime."""

from __future__ import annotations

from .adapter import DryRunAssetRuntimeAdapter
from .models import AssetRequest, AssetResult


def execute_asset_dry_run(request: AssetRequest) -> AssetResult:
    """Execute an asset request in dry-run mode.

    Uses the tracked capability registry to determine what can be handled.
    No external network calls are made. Returns a result with
    status='dry_run' for known capabilities, or status='failed' for unknown.

    Args:
        request: The asset request to execute in dry-run mode.

    Returns:
        AssetResult with status='dry_run' or 'failed'.
    """
    adapter = DryRunAssetRuntimeAdapter()
    return adapter.execute(request)
