"""Asset runtime adapter interface and implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import AssetCapability, AssetRequest, AssetResult


class AssetRuntimeAdapter(ABC):
    """Abstract base class for asset runtime adapters."""

    @abstractmethod
    def list_capabilities(self) -> list[AssetCapability]:
        """Return the list of capabilities this adapter supports."""
        raise NotImplementedError

    @abstractmethod
    def can_handle(self, request: AssetRequest) -> bool:
        """Return True if this adapter can handle the given request."""
        raise NotImplementedError

    @abstractmethod
    def execute(self, request: AssetRequest) -> AssetResult:
        """Execute the asset request and return a result."""
        raise NotImplementedError


class DryRunAssetRuntimeAdapter(AssetRuntimeAdapter):
    """No-op asset runtime adapter for dry-run mode.

    Does not make any external network calls. Always returns a
    dry_run status result without invoking real agents or services.
    """

    def list_capabilities(self) -> list[AssetCapability]:
        return [
            AssetCapability(
                name="asset_resolution",
                description="Resolve asset references and return metadata",
                supported=True,
                dry_run_only=True,
            ),
            AssetCapability(
                name="asset_validation",
                description="Validate asset existence and accessibility",
                supported=True,
                dry_run_only=True,
            ),
        ]

    def can_handle(self, request: AssetRequest) -> bool:
        return request.dry_run is True

    def execute(self, request: AssetRequest) -> AssetResult:
        return AssetResult(
            request_id=request.id,
            status="dry_run",
            capability=None,
            dry_run=True,
            message=f"Dry-run adapter: would handle {request.mode} mode for reason '{request.reason}'",
            artifacts=[],
            warnings=["Dry-run mode — no real agent invoked"],
        )
