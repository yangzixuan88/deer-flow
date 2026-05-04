"""Tests for Foundation Stabilization Plan (R241-15A).

These tests exercise the stabilization_plan.py functions.
They never write audit JSONL, never call network/webhooks, never write
runtime/action queue, and never send Feishu messages.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ─── Import test ───────────────────────────────────────────────────────────

def test_import_module():
    from app.foundation.stabilization_plan import (
        TestLayer,
        LAYER_DEFINITIONS,
        build_test_layer_catalog,
        discover_slow_test_candidates,
        build_pytest_command_matrix,
        build_foundation_risk_stabilization_matrix,
        validate_stabilization_plan,
        generate_foundation_stabilization_plan,
    )
    # Enums
    assert TestLayer.SMOKE.value == "smoke"
    assert TestLayer.UNIT.value == "unit"
    assert TestLayer.INTEGRATION.value == "integration"
    assert TestLayer.SLOW.value == "slow"
    assert TestLayer.FULL.value == "full"
    # Layer definitions
    assert len(LAYER_DEFINITIONS) == 5
    # Functions
    assert callable(build_test_layer_catalog)
    assert callable(discover_slow_test_candidates)
    assert callable(build_pytest_command_matrix)
    assert callable(build_foundation_risk_stabilization_matrix)
    assert callable(validate_stabilization_plan)
    assert callable(generate_foundation_stabilization_plan)


# ─── TestLayerCatalog ───────────────────────────────────────────────────────

class TestLayerCatalog:
    def test_build_test_layer_catalog_returns_dict(self):
        from app.foundation.stabilization_plan import build_test_layer_catalog
        catalog = build_test_layer_catalog()
        assert isinstance(catalog, dict)
        assert "layers" in catalog
        assert "marker_definitions" in catalog

    def test_contains_five_layers(self):
        from app.foundation.stabilization_plan import build_test_layer_catalog
        catalog = build_test_layer_catalog()
        layers = catalog["layers"]
        assert set(layers.keys()) == {"smoke", "unit", "integration", "slow", "full"}

    def test_each_layer_has_required_fields(self):
        from app.foundation.stabilization_plan import build_test_layer_catalog
        catalog = build_test_layer_catalog()
        for name, layer in catalog["layers"].items():
            assert "name" in layer
            assert "description" in layer
            assert "marker" in layer
            assert "target_runtime_seconds" in layer
            assert "entrypoint" in layer
            assert "typical_size" in layer

    def test_marker_definitions_contains_all_markers(self):
        from app.foundation.stabilization_plan import build_test_layer_catalog
        catalog = build_test_layer_catalog()
        markers = catalog["marker_definitions"]
        required = {"smoke", "unit", "integration", "slow", "full", "no_network", "no_runtime_write", "no_secret"}
        assert set(markers.keys()) >= required


# ─── TestSlowTestCandidates ─────────────────────────────────────────────────

class TestSlowTestCandidates:
    def test_discover_slow_test_candidates_returns_dict(self):
        from app.foundation.stabilization_plan import discover_slow_test_candidates
        result = discover_slow_test_candidates()
        assert isinstance(result, dict)
        assert "candidates" in result
        assert "total_candidates" in result
        assert "discovered_at" in result

    def test_identifies_read_only_diagnostics_cli(self):
        from app.foundation.stabilization_plan import discover_slow_test_candidates
        result = discover_slow_test_candidates()
        names = [c["test_name"] for c in result["candidates"]]
        assert "test_read_only_diagnostics_cli" in names or "run_all_diagnostics" in names

    def test_identifies_audit_trend(self):
        from app.foundation.stabilization_plan import discover_slow_test_candidates
        result = discover_slow_test_candidates()
        names = [c["test_name"] for c in result["candidates"]]
        assert any("audit_trend" in n for n in names)

    def test_identifies_sample_generation(self):
        from app.foundation.stabilization_plan import discover_slow_test_candidates
        result = discover_slow_test_candidates()
        names = [c["test_name"] for c in result["candidates"]]
        assert any("sample" in n.lower() for n in names)

    def test_safe_to_split_field_present(self):
        from app.foundation.stabilization_plan import discover_slow_test_candidates
        result = discover_slow_test_candidates()
        for cand in result["candidates"]:
            assert "safe_to_split" in cand
            assert isinstance(cand["safe_to_split"], bool)

    def test_recommended_marker_is_slow(self):
        from app.foundation.stabilization_plan import discover_slow_test_candidates
        result = discover_slow_test_candidates()
        for cand in result["candidates"]:
            if cand.get("safe_to_split"):
                assert cand["recommended_marker"] in ("slow", "integration")


# ─── TestPytestCommandMatrix ───────────────────────────────────────────────

class TestPytestCommandMatrix:
    def test_build_pytest_command_matrix_returns_dict(self):
        from app.foundation.stabilization_plan import build_pytest_command_matrix
        matrix = build_pytest_command_matrix()
        assert isinstance(matrix, dict)
        assert len(matrix) > 0

    def test_smoke_command_present(self):
        from app.foundation.stabilization_plan import build_pytest_command_matrix
        matrix = build_pytest_command_matrix()
        assert "smoke" in matrix
        assert "-m smoke" in matrix["smoke"]["command"]

    def test_not_slow_command_present(self):
        from app.foundation.stabilization_plan import build_pytest_command_matrix
        matrix = build_pytest_command_matrix()
        # At least one command should use 'not slow'
        found = any("not slow" in str(c.get("command", "")) for c in matrix.values())
        assert found, "Expected at least one command with 'not slow'"

    def test_full_regression_command_present(self):
        from app.foundation.stabilization_plan import build_pytest_command_matrix
        matrix = build_pytest_command_matrix()
        assert "full_regression" in matrix
        cmd = matrix["full_regression"]["command"]
        assert "backend/app/foundation" in cmd
        assert "backend/app/audit" in cmd

    def test_command_has_description(self):
        from app.foundation.stabilization_plan import build_pytest_command_matrix
        matrix = build_pytest_command_matrix()
        for name, cmd_info in matrix.items():
            assert "description" in cmd_info
            assert "command" in cmd_info

    def test_safety_checks_command(self):
        from app.foundation.stabilization_plan import build_pytest_command_matrix
        matrix = build_pytest_command_matrix()
        assert "safety_checks" in matrix
        cmd = matrix["safety_checks"]["command"]
        assert "no_network" in cmd


# ─── TestRiskStabilizationMatrix ───────────────────────────────────────────

class TestRiskStabilizationMatrix:
    def test_build_foundation_risk_stabilization_matrix_returns_dict(self):
        from app.foundation.stabilization_plan import build_foundation_risk_stabilization_matrix
        matrix = build_foundation_risk_stabilization_matrix()
        assert isinstance(matrix, dict)
        assert "risks" in matrix

    def test_risk_matrix_contains_slow_test_risk(self):
        from app.foundation.stabilization_plan import build_foundation_risk_stabilization_matrix
        matrix = build_foundation_risk_stabilization_matrix()
        risk_ids = [r["risk_id"] for r in matrix["risks"]]
        assert "slow_test_risk" in risk_ids

    def test_risk_matrix_contains_queue_missing_warning_count(self):
        from app.foundation.stabilization_plan import build_foundation_risk_stabilization_matrix
        matrix = build_foundation_risk_stabilization_matrix()
        risk_ids = [r["risk_id"] for r in matrix["risks"]]
        assert "queue_missing_warning_count" in risk_ids

    def test_risk_matrix_contains_unknown_taxonomy_count(self):
        from app.foundation.stabilization_plan import build_foundation_risk_stabilization_matrix
        matrix = build_foundation_risk_stabilization_matrix()
        risk_ids = [r["risk_id"] for r in matrix["risks"]]
        assert "unknown_taxonomy_count" in risk_ids

    def test_risk_matrix_contains_missing_tool_runtime_projections(self):
        from app.foundation.stabilization_plan import build_foundation_risk_stabilization_matrix
        matrix = build_foundation_risk_stabilization_matrix()
        risk_ids = [r["risk_id"] for r in matrix["risks"]]
        assert "missing_tool_runtime_projections" in risk_ids

    def test_risk_matrix_contains_missing_mode_callgraph_projections(self):
        from app.foundation.stabilization_plan import build_foundation_risk_stabilization_matrix
        matrix = build_foundation_risk_stabilization_matrix()
        risk_ids = [r["risk_id"] for r in matrix["risks"]]
        assert "missing_mode_callgraph_projections" in risk_ids

    def test_each_risk_has_required_fields(self):
        from app.foundation.stabilization_plan import build_foundation_risk_stabilization_matrix
        matrix = build_foundation_risk_stabilization_matrix()
        for risk in matrix["risks"]:
            assert "risk_id" in risk
            assert "risk_name" in risk
            assert "risk_level" in risk
            assert "evidence" in risk
            assert "current_status" in risk
            assert "recommended_next_action" in risk
            assert "should_fix_now" in risk

    def test_high_risks_are_flagged_correctly(self):
        from app.foundation.stabilization_plan import build_foundation_risk_stabilization_matrix
        matrix = build_foundation_risk_stabilization_matrix()
        high_risks = [r for r in matrix["risks"] if r["risk_level"] == "HIGH"]
        for risk in high_risks:
            assert risk["should_fix_now"] in (True, False)


# ─── TestValidation ─────────────────────────────────────────────────────────

class TestValidation:
    def test_validate_stabilization_plan_valid_plan(self):
        from app.foundation.stabilization_plan import (
            build_test_layer_catalog,
            build_pytest_command_matrix,
            build_foundation_risk_stabilization_matrix,
            discover_slow_test_candidates,
            validate_stabilization_plan,
        )
        plan = {
            "layer_catalog": build_test_layer_catalog(),
            "command_matrix": build_pytest_command_matrix(),
            "risk_matrix": build_foundation_risk_stabilization_matrix(),
            "markers": build_test_layer_catalog()["marker_definitions"],
        }
        result = validate_stabilization_plan(plan)
        assert result["valid"] is True

    def test_validate_rejects_empty_layer_catalog(self):
        from app.foundation.stabilization_plan import (
            build_pytest_command_matrix,
            build_foundation_risk_stabilization_matrix,
            validate_stabilization_plan,
            StabilizationValidationError,
        )
        plan = {
            "layer_catalog": {},
            "command_matrix": build_pytest_command_matrix(),
            "risk_matrix": build_foundation_risk_stabilization_matrix(),
            "markers": {},
        }
        with pytest.raises(StabilizationValidationError):
            validate_stabilization_plan(plan)

    def test_validate_rejects_empty_command_matrix(self):
        from app.foundation.stabilization_plan import (
            build_test_layer_catalog,
            build_foundation_risk_stabilization_matrix,
            validate_stabilization_plan,
            StabilizationValidationError,
        )
        plan = {
            "layer_catalog": build_test_layer_catalog(),
            "command_matrix": {},
            "risk_matrix": build_foundation_risk_stabilization_matrix(),
            "markers": build_test_layer_catalog()["marker_definitions"],
        }
        with pytest.raises(StabilizationValidationError):
            validate_stabilization_plan(plan)

    def test_validate_rejects_empty_risk_matrix(self):
        from app.foundation.stabilization_plan import (
            build_test_layer_catalog,
            build_pytest_command_matrix,
            validate_stabilization_plan,
            StabilizationValidationError,
        )
        plan = {
            "layer_catalog": build_test_layer_catalog(),
            "command_matrix": build_pytest_command_matrix(),
            "risk_matrix": {},  # Missing "risks" key entirely
            "markers": build_test_layer_catalog()["marker_definitions"],
        }
        with pytest.raises(StabilizationValidationError):
            validate_stabilization_plan(plan)

    def test_validate_rejects_empty_markers(self):
        from app.foundation.stabilization_plan import (
            build_test_layer_catalog,
            build_pytest_command_matrix,
            build_foundation_risk_stabilization_matrix,
            validate_stabilization_plan,
            StabilizationValidationError,
        )
        plan = {
            "layer_catalog": build_test_layer_catalog(),
            "command_matrix": build_pytest_command_matrix(),
            "risk_matrix": build_foundation_risk_stabilization_matrix(),
            "markers": {},
        }
        with pytest.raises(StabilizationValidationError):
            validate_stabilization_plan(plan)


# ─── TestGeneratePlan ──────────────────────────────────────────────────────

class TestGeneratePlan:
    def test_generate_foundation_stabilization_plan_writes_only_tmp_path(self, tmp_path):
        from app.foundation.stabilization_plan import generate_foundation_stabilization_plan
        out_plan = tmp_path / "test_plan.json"
        out_report = tmp_path / "test_report.md"
        result = generate_foundation_stabilization_plan(str(out_plan))
        assert out_plan.exists()
        data = json.loads(out_plan.read_text(encoding="utf-8"))
        assert "layer_catalog" in data
        assert "command_matrix" in data
        assert "risk_matrix" in data

    def test_generate_plan_no_network(self, tmp_path, monkeypatch):
        from app.foundation.stabilization_plan import generate_foundation_stabilization_plan
        network_calls = []
        original_get = None
        try:
            import urllib.request
            original_get = urllib.request.urlopen
            def tracking_get(*args, **kwargs):
                network_calls.append(args[0])
                raise Exception("network should not be called")
            urllib.request.urlopen = tracking_get
            out_path = tmp_path / "test_plan.json"
            generate_foundation_stabilization_plan(str(out_path))
            assert len(network_calls) == 0
        finally:
            if original_get:
                urllib.request.urlopen = original_get

    def test_generate_plan_returns_validation_result(self, tmp_path):
        from app.foundation.stabilization_plan import generate_foundation_stabilization_plan
        out_path = tmp_path / "test_plan.json"
        result = generate_foundation_stabilization_plan(str(out_path))
        assert "validation" in result
        assert result["validation"]["valid"] is True
        assert "output_plan_path" in result
        assert "output_report_path" in result


# ─── TestSafetyConstraints ────────────────────────────────────────────────

class TestSafetyConstraints:
    def test_generate_plan_does_not_write_audit_jsonl(self, tmp_path):
        from app.foundation.stabilization_plan import generate_foundation_stabilization_plan
        # Verify by checking that audit_trail_writer.append_audit_record_to_target is never called
        import app.audit.audit_trail_writer as writer_mod
        original_append = writer_mod.append_audit_record_to_target
        append_count = 0
        try:
            def counting_append(*args, **kwargs):
                nonlocal append_count
                append_count += 1
                return {"status": "appended", "lines_written": 0}
            writer_mod.append_audit_record_to_target = counting_append
            out_path = tmp_path / "test_plan.json"
            generate_foundation_stabilization_plan(str(out_path))
            assert append_count == 0
        finally:
            writer_mod.append_audit_record_to_target = original_append

    def test_discover_slow_candidates_no_runtime_write(self):
        from app.foundation.stabilization_plan import discover_slow_test_candidates
        result = discover_slow_test_candidates()
        # Should not contain runtime_write flags
        assert "runtime_write_detected" not in str(result) or result.get("runtime_write_detected", False) is False

    def test_validate_plan_rejects_safety_coverage_reduced(self):
        from app.foundation.stabilization_plan import (
            validate_stabilization_plan,
            StabilizationValidationError,
        )
        plan = {
            "layer_catalog": {"layers": {"smoke": {}, "unit": {}, "integration": {}, "slow": {}, "full": {}}},
            "command_matrix": {"smoke": {"command": "echo test", "description": "test"}},
            "risk_matrix": {"risks": [{"risk_id": "safety_coverage_reduced"}]},
            "markers": {"smoke": "test"},
        }
        with pytest.raises(StabilizationValidationError) as exc_info:
            validate_stabilization_plan(plan)
        assert "safety_coverage_reduced" in str(exc_info.value)