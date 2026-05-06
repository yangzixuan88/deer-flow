"""Asset capability registry.

Provides a typed registry for asset capabilities loaded from tracked
metadata. Never reads from .deerflow/operation_assets/ or external/Agent-S/.
"""

from __future__ import annotations

import json
from pathlib import Path

from .capabilities import get_default_capabilities_path
from .models import AssetCapability


class AssetCapabilityRegistry:
    """Registry of asset capabilities loaded from tracked metadata."""

    def __init__(self, capabilities: list[AssetCapability]) -> None:
        self._capabilities = {c.name: c for c in capabilities}

    @classmethod
    def from_default(cls) -> AssetCapabilityRegistry:
        """Load capabilities from the package-tracked default_capabilities.json.

        Uses importlib.resources to read from the capabilities package.
        Does not read .deerflow/operation_assets/ or external/Agent-S/.
        """
        capabilities_path = get_default_capabilities_path()
        with capabilities_path.open() as f:
            raw_list = json.load(f)

        capabilities = [validate_capability_payload(raw) for raw in raw_list]
        return cls(capabilities)

    @classmethod
    def from_file(cls, path: str | Path) -> AssetCapabilityRegistry:
        """Load capabilities from an explicit file path.

        Only use this for testing or explicit operator-supplied paths.
        The path must not be inside .deerflow/operation_assets/.

        Args:
            path: Path to a JSON file containing capability list.

        Raises:
            ValueError: If path is inside .deerflow/operation_assets/.
        """
        p = Path(path).resolve()
        if ".deerflow" in p.parts and "operation_assets" in p.parts:
            raise ValueError("Loading capabilities from .deerflow/operation_assets/ is not allowed")
        with p.open() as f:
            raw_list = json.load(f)
        capabilities = [validate_capability_payload(raw) for raw in raw_list]
        return cls(capabilities)

    def list_capabilities(self) -> list[AssetCapability]:
        """Return all registered capabilities."""
        return list(self._capabilities.values())

    def get(self, name: str) -> AssetCapability | None:
        """Get a capability by name, or None if not found."""
        return self._capabilities.get(name)

    def require(self, name: str) -> AssetCapability:
        """Get a capability by name, raising KeyError if not found."""
        cap = self._capabilities.get(name)
        if cap is None:
            raise KeyError(f"Unknown capability: {name}")
        return cap

    def list_supported(self) -> list[AssetCapability]:
        """Return only supported capabilities."""
        return [c for c in self._capabilities.values() if c.supported]

    def list_by_category(self, category: str) -> list[AssetCapability]:
        """Return capabilities in a specific category."""
        return [c for c in self._capabilities.values() if c.category == category]


def validate_capability_payload(raw: dict) -> AssetCapability:
    """Validate and construct an AssetCapability from a raw dict.

    Args:
        raw: Dictionary with capability fields.

    Returns:
        Validated AssetCapability instance.

    Raises:
        ValueError: If name or description is missing.
    """
    if not raw.get("name"):
        raise ValueError("capability 'name' is required")
    if not raw.get("description"):
        raise ValueError("capability 'description' is required")
    return AssetCapability.from_dict(raw)
