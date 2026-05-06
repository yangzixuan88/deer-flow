"""Dry-run execution helpers for asset runtime."""

from __future__ import annotations

from .adapter import DryRunAssetRuntimeAdapter
from .models import AssetRequest, AssetResult


def execute_asset_dry_run(request: AssetRequest) -> AssetResult:
    """Execute an asset request in dry-run mode.

    No external network calls are made. Returns a result with
    status='dry_run' indicating the request was validated but not processed.

    Args:
        request: The asset request to execute in dry-run mode.

    Returns:
        AssetResult with status='dry_run' and a descriptive message.
    """
    adapter = DryRunAssetRuntimeAdapter()
    return adapter.execute(request)
