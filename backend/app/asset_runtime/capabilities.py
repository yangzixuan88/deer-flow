"""Asset capability facade.

Provides a lightweight API for accessing the default capability registry
without importing the full registry module. Never reads from
.deerflow/operation_assets/ or external/Agent-S/.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import AssetCapability
    from .registry import AssetCapabilityRegistry


def get_default_capabilities_path() -> Path:
    """Return the Path to the default_capabilities.json inside the package.

    Uses importlib.resources to locate the file inside the
    app.asset_runtime.capability_metadata package.
    """
    ref = resources.files("app.asset_runtime.capability_metadata")
    base = ref / "default_capabilities.json"
    if isinstance(base, Path):
        return base
    path = Path(base)
    if path.exists():
        return path
    module_path = ref.joinpath("default_capabilities.json")
    if hasattr(module_path, "__fspath__"):
        return Path(module_path.__fspath__())
    return Path(str(module_path))


def get_default_registry() -> AssetCapabilityRegistry:
    """Return the default capability registry singleton.

    Lazily loads from package-tracked default_capabilities.json.
    """
    from .registry import AssetCapabilityRegistry

    return AssetCapabilityRegistry.from_default()


def list_default_capabilities() -> list[AssetCapability]:
    """Return all default capabilities as AssetCapability instances."""
    registry = get_default_registry()
    return registry.list_capabilities()


def get_default_capability(name: str) -> AssetCapability | None:
    """Get a named default capability, or None if not found."""
    registry = get_default_registry()
    return registry.get(name)
