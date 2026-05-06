"""Asset runtime adapter package.

Scope (R221):
- AssetRuntimeAdapter interface
- DryRunAssetRuntimeAdapter (no-op, no external calls)
- models: AssetRequest, AssetResult, AssetCapability, AssetRuntimeStatus
- integration helpers

Out of scope for R221:
- Real Agent-S invocation
- Untracked operation_assets reads
- Feishu/Lark real-send
- Scheduler daemon
"""

from __future__ import annotations

from .adapter import AssetRuntimeAdapter, DryRunAssetRuntimeAdapter
from .dry_run import execute_asset_dry_run
from .integration import execute_asset_dry_run as execute_asset_dry_run_fn
from .integration import mode_decision_to_asset_request
from .models import (
    AssetCapability,
    AssetRequest,
    AssetResult,
    AssetRuntimeStatus,
)

__all__ = [
    "AssetCapability",
    "AssetRequest",
    "AssetResult",
    "AssetRuntimeAdapter",
    "AssetRuntimeStatus",
    "DryRunAssetRuntimeAdapter",
    "execute_asset_dry_run",
    "execute_asset_dry_run_fn",
    "mode_decision_to_asset_request",
]
