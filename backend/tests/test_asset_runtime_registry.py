"""Tests for asset capability registry.

Verifies that the registry loads from tracked metadata, validates
capability payloads, and never reads .deerflow/operation_assets/ or
external/Agent-S/.
"""

from __future__ import annotations

import json

import pytest

from app.asset_runtime.capabilities import get_default_capabilities_path
from app.asset_runtime.registry import (
    AssetCapabilityRegistry,
    validate_capability_payload,
)

# =============================================================================
# Default registry tests
# =============================================================================


class TestDefaultRegistry:
    def test_default_registry_loads_tracked_capabilities(self):
        registry = AssetCapabilityRegistry.from_default()
        assert len(registry.list_capabilities()) >= 6

    def test_default_registry_has_expected_capabilities(self):
        registry = AssetCapabilityRegistry.from_default()
        names = {c.name for c in registry.list_capabilities()}
        assert "asset.noop" in names
        assert "asset.plan" in names
        assert "asset.preview" in names
        assert "asset.validate" in names
        assert "asset.package" in names
        assert "asset.publish" in names

    def test_default_capabilities_are_json_serializable(self):
        registry = AssetCapabilityRegistry.from_default()
        for cap in registry.list_capabilities():
            d = cap.to_dict()
            assert isinstance(d, dict)
            json.dumps(d)


# =============================================================================
# Capability validation tests
# =============================================================================


class TestCapabilityValidation:
    def test_capability_payload_validation_requires_name(self):
        raw = {"description": "test"}
        with pytest.raises(ValueError, match="'name' is required"):
            validate_capability_payload(raw)

    def test_capability_payload_validation_requires_description(self):
        raw = {"name": "test.capability"}
        with pytest.raises(ValueError, match="'description' is required"):
            validate_capability_payload(raw)

    def test_capability_payload_validation_accepts_valid(self):
        raw = {
            "name": "test.capability",
            "description": "A test capability",
            "category": "testing",
            "supported": True,
            "dry_run_only": True,
            "requires_external_runtime": False,
            "inputs": ["input1"],
            "outputs": ["output1"],
            "warnings": ["warn1"],
        }
        cap = validate_capability_payload(raw)
        assert cap.name == "test.capability"
        assert cap.description == "A test capability"
        assert cap.category == "testing"
        assert cap.inputs == ["input1"]
        assert cap.outputs == ["output1"]


# =============================================================================
# Registry access tests
# =============================================================================


class TestRegistryAccess:
    def test_registry_get_known_capability(self):
        registry = AssetCapabilityRegistry.from_default()
        cap = registry.get("asset.noop")
        assert cap is not None
        assert cap.name == "asset.noop"

    def test_registry_get_unknown_returns_none(self):
        registry = AssetCapabilityRegistry.from_default()
        cap = registry.get("asset.unknown")
        assert cap is None

    def test_registry_require_known_capability(self):
        registry = AssetCapabilityRegistry.from_default()
        cap = registry.require("asset.plan")
        assert cap.name == "asset.plan"

    def test_registry_require_unknown_raises(self):
        registry = AssetCapabilityRegistry.from_default()
        with pytest.raises(KeyError, match="Unknown capability"):
            registry.require("asset.does_not_exist")

    def test_registry_list_supported(self):
        registry = AssetCapabilityRegistry.from_default()
        supported = registry.list_supported()
        assert all(c.supported for c in supported)
        assert len(supported) >= 6

    def test_registry_list_by_category(self):
        registry = AssetCapabilityRegistry.from_default()
        planning = registry.list_by_category("planning")
        assert len(planning) >= 1
        assert all(c.category == "planning" for c in planning)


# =============================================================================
# File loading tests
# =============================================================================


class TestRegistryFileLoading:
    def test_registry_from_file_uses_explicit_path(self, tmp_path):
        cap_file = tmp_path / "custom_caps.json"
        cap_file.write_text(
            json.dumps(
                [
                    {
                        "name": "custom.cap",
                        "description": "A custom capability",
                        "category": "custom",
                        "supported": True,
                        "dry_run_only": True,
                        "requires_external_runtime": False,
                    }
                ]
            )
        )
        registry = AssetCapabilityRegistry.from_file(str(cap_file))
        assert registry.get("custom.cap") is not None

    def test_registry_rejects_operation_assets_path(self):
        with pytest.raises(ValueError, match="operation_assets"):
            AssetCapabilityRegistry.from_file("/some/path/.deerflow/operation_assets/capabilities.json")


# =============================================================================
# Safety tests
# =============================================================================


class TestRegistrySafety:
    def test_default_registry_does_not_read_operation_assets(self, monkeypatch):
        opened_paths: list[str] = []

        def tracking_open(path, *args, **kwargs):
            p = str(path)
            opened_paths.append(p)
            raise FileNotFoundError("blocked for test")

        monkeypatch.setattr("builtins.open", tracking_open)
        AssetCapabilityRegistry.from_default()

        for p in opened_paths:
            assert ".deerflow/operation_assets" not in p

    def test_default_registry_path_does_not_reference_agent_s(self):

        path = str(get_default_capabilities_path())
        assert "Agent-S" not in path

    def test_no_credentials_or_tokens_in_default_capabilities(self):
        registry = AssetCapabilityRegistry.from_default()
        for cap in registry.list_capabilities():
            d = json.dumps(cap.to_dict()).lower()
            assert "token" not in d
            assert "secret" not in d
            assert "password" not in d
            assert "apikey" not in d
            assert "ghp_" not in d

    def test_registry_import_has_no_side_effects(self):
        import importlib

        import app.asset_runtime.capabilities
        import app.asset_runtime.registry

        importlib.reload(app.asset_runtime.registry)
        importlib.reload(app.asset_runtime.capabilities)

        registry = AssetCapabilityRegistry.from_default()
        assert len(registry.list_capabilities()) >= 6

    def test_registry_no_network_required(self, monkeypatch):
        called_network = []

        def blocking_http_get(*args, **kwargs):
            called_network.append(args)
            raise ConnectionError("network blocked for test")

        monkeypatch.setattr("urllib.request.urlopen", blocking_http_get)
        registry = AssetCapabilityRegistry.from_default()
        caps = registry.list_capabilities()
        assert len(caps) >= 6
        assert len(called_network) == 0

    def test_external_required_capabilities_are_dry_run_only(self):
        registry = AssetCapabilityRegistry.from_default()
        for cap in registry.list_capabilities():
            if cap.requires_external_runtime:
                assert cap.dry_run_only is True
