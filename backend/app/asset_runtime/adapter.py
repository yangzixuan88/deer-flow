"""Asset runtime adapter interface and implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from .models import AssetCapability, AssetRequest, AssetResult

if TYPE_CHECKING:
    from .registry import AssetCapabilityRegistry


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
    """Dry-run asset runtime adapter backed by the tracked capability registry.

    Does not make any external network calls. Always returns a dry_run
    status result without invoking real agents or services.
    """

    def __init__(self, registry: AssetCapabilityRegistry | None = None) -> None:
        from .registry import AssetCapabilityRegistry

        if registry is None:
            registry = AssetCapabilityRegistry.from_default()
        self._registry = registry

    def list_capabilities(self) -> list[AssetCapability]:
        return self._registry.list_capabilities()

    def can_handle(self, request: AssetRequest) -> bool:
        if not request.dry_run:
            return False
        if request.requested_capability is None:
            return True
        cap = self._registry.get(request.requested_capability)
        return cap is not None and cap.supported

    def execute(self, request: AssetRequest) -> AssetResult:
        capability_name = request.requested_capability or "asset.noop"
        cap = self._registry.get(capability_name)

        if cap is None:
            return AssetResult(
                request_id=request.id,
                status="failed",
                capability=capability_name,
                dry_run=True,
                message=f"Unknown capability: {capability_name}",
                artifacts=[],
                warnings=["Unknown capability — dry-run failed safely"],
            )

        warnings = list(cap.warnings) if cap.warnings else []
        warnings.append("Dry-run mode — no real agent invoked")

        if cap.requires_external_runtime:
            warnings.append("external Agent-S runtime not invoked in dry-run mode")

        return AssetResult(
            request_id=request.id,
            status="dry_run",
            capability=cap.name,
            dry_run=True,
            message=f"Dry-run adapter: {cap.description} for reason '{request.reason}'",
            artifacts=[],
            warnings=warnings,
        )
