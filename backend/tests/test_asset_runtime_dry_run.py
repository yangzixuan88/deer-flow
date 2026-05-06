"""Tests for asset runtime dry-run adapter and integration helpers."""

from __future__ import annotations

import pytest

from app.asset_runtime import (
    AssetCapability,
    AssetRequest,
    AssetResult,
    AssetRuntimeAdapter,
    AssetRuntimeStatus,
    DryRunAssetRuntimeAdapter,
    execute_asset_dry_run,
    mode_decision_to_asset_request,
)

# =============================================================================
# AssetRuntimeStatus constants
# =============================================================================


class TestAssetRuntimeStatus:
    def test_status_constants_defined(self):
        assert AssetRuntimeStatus.UNAVAILABLE == "unavailable"
        assert AssetRuntimeStatus.DRY_RUN == "dry_run"
        assert AssetRuntimeStatus.EXTERNAL_REQUIRED == "external_required"
        assert AssetRuntimeStatus.FAILED == "failed"
        assert AssetRuntimeStatus.COMPLETED == "completed"


# =============================================================================
# AssetCapability
# =============================================================================


class TestAssetCapability:
    def test_to_dict_roundtrip(self):
        cap = AssetCapability(
            name="test_cap",
            description="A test capability",
            supported=True,
            dry_run_only=False,
        )
        d = cap.to_dict()
        restored = AssetCapability.from_dict(d)
        assert restored.name == cap.name
        assert restored.description == cap.description
        assert restored.supported == cap.supported
        assert restored.dry_run_only == cap.dry_run_only

    def test_defaults(self):
        cap = AssetCapability(name="x", description="y")
        assert cap.supported is True
        assert cap.dry_run_only is True


# =============================================================================
# AssetRequest
# =============================================================================


class TestAssetRequest:
    def test_new_generates_uuid(self):
        req1 = AssetRequest.new(mode="test", reason="testing")
        req2 = AssetRequest.new(mode="test", reason="testing")
        assert req1.id != req2.id
        assert len(req1.id) == 36  # UUID format

    def test_new_defaults(self):
        req = AssetRequest.new(mode="asset", reason="test-reason")
        assert req.user_id is None
        assert req.thread_id is None
        assert req.run_id is None
        assert req.requested_capability is None
        assert req.payload_summary == ""
        assert req.source == "mode_router"
        assert req.dry_run is True

    def test_new_accepts_all_fields(self):
        req = AssetRequest.new(
            mode="delegated",
            reason="full test",
            user_id="user-123",
            thread_id="thread-456",
            run_id="run-789",
            requested_capability="asset_resolution",
            payload_summary="Test payload summary",
            source="custom_source",
            dry_run=False,
        )
        assert req.mode == "delegated"
        assert req.user_id == "user-123"
        assert req.thread_id == "thread-456"
        assert req.run_id == "run-789"
        assert req.requested_capability == "asset_resolution"
        assert req.payload_summary == "Test payload summary"
        assert req.source == "custom_source"
        assert req.dry_run is False

    def test_to_dict_roundtrip(self):
        req = AssetRequest.new(mode="test", reason="testing", dry_run=False)
        d = req.to_dict()
        restored = AssetRequest.from_dict(d)
        assert restored.id == req.id
        assert restored.mode == req.mode
        assert restored.dry_run == req.dry_run


# =============================================================================
# AssetResult
# =============================================================================


class TestAssetResult:
    def test_to_dict_roundtrip(self):
        result = AssetResult(
            request_id="req-1",
            status=AssetRuntimeStatus.DRY_RUN,
            capability="asset_resolution",
            dry_run=True,
            message="dry run message",
            artifacts=["artifact-1"],
            warnings=["warning-1"],
        )
        d = result.to_dict()
        restored = AssetResult.from_dict(d)
        assert restored.request_id == result.request_id
        assert restored.status == result.status
        assert restored.artifacts == result.artifacts
        assert restored.warnings == result.warnings

    def test_from_dict_handles_missing_artifacts_and_warnings(self):
        # Simulates dict without artifacts/warnings keys (e.g. from some serializations)
        d = {
            "request_id": "req-2",
            "status": "completed",
            "capability": None,
            "dry_run": False,
            "message": "done",
        }
        restored = AssetResult.from_dict(d)
        assert restored.artifacts == []
        assert restored.warnings == []


# =============================================================================
# DryRunAssetRuntimeAdapter
# =============================================================================


class TestDryRunAssetRuntimeAdapter:
    def test_list_capabilities_returns_list(self):
        adapter = DryRunAssetRuntimeAdapter()
        caps = adapter.list_capabilities()
        assert isinstance(caps, list)
        assert len(caps) >= 2
        assert all(isinstance(c, AssetCapability) for c in caps)

    def test_list_capabilities_contains_expected_names(self):
        adapter = DryRunAssetRuntimeAdapter()
        names = {c.name for c in adapter.list_capabilities()}
        assert "asset.noop" in names
        assert "asset.plan" in names
        assert "asset.validate" in names

    def test_can_handle_returns_true_for_dry_run_request(self):
        adapter = DryRunAssetRuntimeAdapter()
        req = AssetRequest.new(mode="asset", reason="test", dry_run=True)
        assert adapter.can_handle(req) is True

    def test_can_handle_returns_false_for_non_dry_run_request(self):
        adapter = DryRunAssetRuntimeAdapter()
        req = AssetRequest.new(mode="asset", reason="test", dry_run=False)
        assert adapter.can_handle(req) is False

    def test_execute_returns_dry_run_status(self):
        adapter = DryRunAssetRuntimeAdapter()
        req = AssetRequest.new(mode="asset", reason="test-reason", dry_run=True)
        result = adapter.execute(req)
        assert result.status == AssetRuntimeStatus.DRY_RUN
        assert result.dry_run is True
        assert "Dry-run adapter" in result.message

    def test_execute_uses_request_id(self):
        adapter = DryRunAssetRuntimeAdapter()
        req = AssetRequest.new(mode="delegated", reason="testing", dry_run=True)
        result = adapter.execute(req)
        assert result.request_id == req.id

    def test_execute_returns_warning(self):
        adapter = DryRunAssetRuntimeAdapter()
        req = AssetRequest.new(mode="asset", reason="test", dry_run=True)
        result = adapter.execute(req)
        assert len(result.warnings) == 1
        assert "Dry-run mode" in result.warnings[0]


# =============================================================================
# execute_asset_dry_run function
# =============================================================================


class TestExecuteAssetDryRun:
    def test_returns_dry_run_result(self):
        req = AssetRequest.new(mode="asset", reason="test", dry_run=True)
        result = execute_asset_dry_run(req)
        assert result.status == AssetRuntimeStatus.DRY_RUN
        assert result.dry_run is True

    def test_returns_result_for_any_valid_request(self):
        req = AssetRequest.new(
            mode="delegated",
            reason="full integration test",
            user_id="user-1",
            thread_id="thread-1",
            run_id="run-1",
            dry_run=True,
        )
        result = execute_asset_dry_run(req)
        assert result.request_id == req.id
        assert isinstance(result.message, str)


# =============================================================================
# mode_decision_to_asset_request helper
# =============================================================================


class TestModeDecisionToAssetRequest:
    def test_returns_asset_request(self):
        req = mode_decision_to_asset_request(
            mode="asset",
            reason="Asset mode routing",
        )
        assert isinstance(req, AssetRequest)

    def test_mode_and_reason_set(self):
        req = mode_decision_to_asset_request(mode="delegated", reason="Handoff to asset agent")
        assert req.mode == "delegated"
        assert req.reason == "Handoff to asset agent"

    def test_all_optional_args_passed_through(self):
        req = mode_decision_to_asset_request(
            mode="asset",
            reason="test",
            user_id="u1",
            thread_id="t1",
            run_id="r1",
            requested_capability="asset_resolution",
            payload_summary="Test summary",
            source="test_source",
            dry_run=False,
        )
        assert req.user_id == "u1"
        assert req.thread_id == "t1"
        assert req.run_id == "r1"
        assert req.requested_capability == "asset_resolution"
        assert req.payload_summary == "Test summary"
        assert req.source == "test_source"
        assert req.dry_run is False

    def test_default_dry_run_true(self):
        req = mode_decision_to_asset_request(mode="asset", reason="test")
        assert req.dry_run is True

    def test_default_source_mode_router(self):
        req = mode_decision_to_asset_request(mode="asset", reason="test")
        assert req.source == "mode_router"


# =============================================================================
# Interface: AssetRuntimeAdapter is abstract
# =============================================================================


class TestAssetRuntimeAdapterInterface:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError) as exc_info:
            AssetRuntimeAdapter()
        assert "abstract" in str(exc_info.value).lower() or "NotImplementedError" in str(exc_info.value)

    def test_subclass_must_implement_all_methods(self):
        class IncompleteAdapter(AssetRuntimeAdapter):
            pass

        with pytest.raises(TypeError):
            IncompleteAdapter()


# =============================================================================
# Registry-aware dry-run tests
# =============================================================================


class TestRegistryAwareDryRun:
    def test_dry_run_adapter_uses_default_registry(self):
        adapter = DryRunAssetRuntimeAdapter()
        caps = adapter.list_capabilities()
        names = {c.name for c in caps}
        assert "asset.noop" in names
        assert "asset.package" in names

    def test_dry_run_adapter_can_handle_known_capability(self):
        adapter = DryRunAssetRuntimeAdapter()
        req = AssetRequest.new(
            mode="asset",
            reason="test",
            dry_run=True,
            requested_capability="asset.plan",
        )
        assert adapter.can_handle(req) is True

    def test_dry_run_adapter_rejects_unknown_capability(self):
        adapter = DryRunAssetRuntimeAdapter()
        req = AssetRequest.new(
            mode="asset",
            reason="test",
            dry_run=True,
            requested_capability="asset.does_not_exist",
        )
        assert adapter.can_handle(req) is False

    def test_execute_known_capability_returns_registry_metadata(self):
        adapter = DryRunAssetRuntimeAdapter()
        req = AssetRequest.new(
            mode="asset",
            reason="test plan capability",
            dry_run=True,
            requested_capability="asset.plan",
        )
        result = adapter.execute(req)
        assert result.capability == "asset.plan"
        assert result.status == "dry_run"

    def test_execute_external_required_capability_warns_not_invoked(self):
        adapter = DryRunAssetRuntimeAdapter()
        req = AssetRequest.new(
            mode="asset",
            reason="test package",
            dry_run=True,
            requested_capability="asset.package",
        )
        result = adapter.execute(req)
        assert result.status == "dry_run"
        assert any("external Agent-S runtime not invoked" in w for w in result.warnings)

    def test_execute_unknown_capability_fails_safely(self):
        adapter = DryRunAssetRuntimeAdapter()
        req = AssetRequest.new(
            mode="asset",
            reason="test",
            dry_run=True,
            requested_capability="asset.unknown_cap",
        )
        result = adapter.execute(req)
        assert result.status == "failed"
        assert "Unknown capability" in result.message

    def test_execute_non_dry_run_still_refused(self):
        adapter = DryRunAssetRuntimeAdapter()
        req = AssetRequest.new(
            mode="asset",
            reason="real execution",
            dry_run=False,
        )
        assert adapter.can_handle(req) is False

    def test_operation_assets_not_read_during_execution(self, monkeypatch):
        opened_paths: list[str] = []

        def tracking_open(path, *args, **kwargs):
            p = str(path)
            opened_paths.append(p)
            raise FileNotFoundError("blocked")

        monkeypatch.setattr("builtins.open", tracking_open)
        adapter = DryRunAssetRuntimeAdapter()
        req = AssetRequest.new(
            mode="asset",
            reason="test",
            dry_run=True,
            requested_capability="asset.validate",
        )
        adapter.execute(req)

        for p in opened_paths:
            assert ".deerflow/operation_assets" not in p
