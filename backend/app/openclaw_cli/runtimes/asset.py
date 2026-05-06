"""Asset runtime wrapper for OpenClaw operator CLI.

Dry-run only — delegates to execute_asset_dry_run without
reading operation_assets, invoking Agent-S, or making network calls.
"""

from __future__ import annotations

from app.asset_runtime import AssetRequest, execute_asset_dry_run

from ..commands import OperatorCommandResult


def run_asset_dry_run(
    *,
    capability: str | None = None,
    payload_summary: str = "OpenClaw operator dry-run",
) -> OperatorCommandResult:
    """Run an Asset dry-run.

    Args:
        capability: Optional capability name override.
        payload_summary: Human-readable summary for the dry-run.

    Returns:
        OperatorCommandResult with dry_run=True and AssetResult payload.
    """
    req = AssetRequest.new(
        mode="asset",
        reason=payload_summary,
        dry_run=True,
    )

    result = execute_asset_dry_run(req)

    payload_dict = result.to_dict()
    if "request_id" in payload_dict:
        del payload_dict["request_id"]

    return OperatorCommandResult(
        command="asset-dry-run",
        status="success",
        dry_run=True,
        payload={
            "request_id": result.request_id,
            "status": result.status,
            "dry_run": result.dry_run,
            "warnings": result.warnings,
            "capability": result.capability,
            "message": result.message,
        },
        warnings=["Dry-run only — no real Agent-S invoked"],
    )