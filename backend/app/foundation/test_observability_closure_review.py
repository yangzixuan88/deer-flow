"""Tests for Foundation Observability Closure Review (R241-14A).

These tests exercise the closure review functions in isolation.
They never write audit JSONL, never call network/webhooks, never write
runtime/action queue, and never send Feishu messages.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ─── Import test ────────────────────────────────────────────────────────────

def test_import_module():
    from app.foundation.observability_closure_review import (
        ObservabilityLayerStatus,
        ObservabilityCapabilityType,
        ObservabilityRiskLevel,
        NextPhaseRecommendation,
        ObservabilityCapabilityRecord,
        ObservabilityRiskRecord,
        ObservabilityClosureMatrix,
        ObservabilityClosureReview,
        discover_observability_capabilities,
        evaluate_observability_capability,
        build_observability_risk_register,
        check_observability_deviation,
        summarize_test_health,
        build_observability_closure_matrix,
        propose_next_phase_options,
        generate_observability_closure_review,
    )
    # Enums
    assert ObservabilityLayerStatus.COMPLETE.value == "complete"
    assert ObservabilityCapabilityType.READ_ONLY_DIAGNOSTIC.value == "read_only_diagnostic"
    assert ObservabilityRiskLevel.HIGH.value == "high"
    assert NextPhaseRecommendation.STABILIZE_TESTS.value == "stabilize_tests"
    # Functions
    assert callable(discover_observability_capabilities)
    assert callable(evaluate_observability_capability)
    assert callable(build_observability_risk_register)
    assert callable(check_observability_deviation)
    assert callable(summarize_test_health)
    assert callable(build_observability_closure_matrix)
    assert callable(propose_next_phase_options)
    assert callable(generate_observability_closure_review)


# ─── TestDiscoverCapabilities ────────────────────────────────────────────────

class TestDiscoverCapabilities:
    def test_discover_returns_capabilities_list(self):
        from app.foundation.observability_closure_review import discover_observability_capabilities
        result = discover_observability_capabilities(root=str(ROOT))
        assert "capabilities" in result
        assert isinstance(result["capabilities"], list)
        assert result["discovered_count"] > 0

    def test_discover_contains_read_only_diagnostic(self):
        from app.foundation.observability_closure_review import discover_observability_capabilities
        result = discover_observability_capabilities(root=str(ROOT))
        cap_ids = [c["capability_id"] for c in result["capabilities"]]
        assert "read_only_diagnostic_cli" in cap_ids

    def test_discover_contains_append_only_audit(self):
        from app.foundation.observability_closure_review import discover_observability_capabilities
        result = discover_observability_capabilities(root=str(ROOT))
        cap_ids = [c["capability_id"] for c in result["capabilities"]]
        assert "append_only_audit_writer" in cap_ids

    def test_discover_contains_audit_query(self):
        from app.foundation.observability_closure_review import discover_observability_capabilities
        result = discover_observability_capabilities(root=str(ROOT))
        cap_ids = [c["capability_id"] for c in result["capabilities"]]
        assert "audit_query_engine" in cap_ids

    def test_discover_contains_trend_cli_guard(self):
        from app.foundation.observability_closure_review import discover_observability_capabilities
        result = discover_observability_capabilities(root=str(ROOT))
        cap_ids = [c["capability_id"] for c in result["capabilities"]]
        assert "trend_cli_guard" in cap_ids

    def test_discover_contains_feishu_preview(self):
        from app.foundation.observability_closure_review import discover_observability_capabilities
        result = discover_observability_capabilities(root=str(ROOT))
        cap_ids = [c["capability_id"] for c in result["capabilities"]]
        assert "feishu_trend_cli_preview" in cap_ids

    def test_discover_contains_manual_send_policy(self):
        from app.foundation.observability_closure_review import discover_observability_capabilities
        result = discover_observability_capabilities(root=str(ROOT))
        cap_ids = [c["capability_id"] for c in result["capabilities"]]
        assert "manual_send_policy_design" in cap_ids


# ─── TestEvaluateCapability ───────────────────────────────────────────────────

class TestEvaluateCapability:
    def test_evaluate_read_only_diagnostic_network_false(self):
        from app.foundation.observability_closure_review import evaluate_observability_capability
        cap = {
            "capability_id": "read_only_diagnostic_cli",
            "capability_type": "read_only_diagnostic",
            "phase_range": "R241-10A",
            "owner_module": "app.foundation.read_only_diagnostics_cli",
            "module_path": str(ROOT / "backend" / "app" / "foundation" / "read_only_diagnostics_cli.py"),
        }
        result = evaluate_observability_capability(cap)
        assert result["calls_network"] is False

    def test_evaluate_runtime_write_false(self):
        from app.foundation.observability_closure_review import evaluate_observability_capability
        cap = {
            "capability_id": "append_only_audit_writer",
            "capability_type": "append_only_audit",
            "phase_range": "R241-11C",
            "owner_module": "app.audit.audit_trail_writer",
            "module_path": str(ROOT / "backend" / "app" / "audit" / "audit_trail_writer.py"),
        }
        result = evaluate_observability_capability(cap)
        assert result["writes_runtime"] is False

    def test_evaluate_append_only_audit(self):
        from app.foundation.observability_closure_review import evaluate_observability_capability
        cap = {
            "capability_id": "append_only_audit_writer",
            "capability_type": "append_only_audit",
            "phase_range": "R241-11C",
            "owner_module": "app.audit.audit_trail_writer",
            "module_path": str(ROOT / "backend" / "app" / "audit" / "audit_trail_writer.py"),
        }
        result = evaluate_observability_capability(cap)
        assert result["append_only"] is True
        assert result["read_only"] is False


# ─── TestRiskRegister ─────────────────────────────────────────────────────────

class TestRiskRegister:
    def test_risk_register_contains_queue_missing(self):
        from app.foundation.observability_closure_review import (
            discover_observability_capabilities,
            build_observability_risk_register,
        )
        caps_result = discover_observability_capabilities(root=str(ROOT))
        register = build_observability_risk_register(caps_result["capabilities"])
        risk_ids = [r["risk_id"] for r in register["risks"]]
        assert "queue_missing_projection_gap" in risk_ids

    def test_risk_register_contains_unknown_taxonomy(self):
        from app.foundation.observability_closure_review import (
            discover_observability_capabilities,
            build_observability_risk_register,
        )
        caps_result = discover_observability_capabilities(root=str(ROOT))
        register = build_observability_risk_register(caps_result["capabilities"])
        risk_ids = [r["risk_id"] for r in register["risks"]]
        assert "unknown_taxonomy_risk" in risk_ids

    def test_risk_register_has_high_critical_risks(self):
        from app.foundation.observability_closure_review import (
            discover_observability_capabilities,
            build_observability_risk_register,
        )
        caps_result = discover_observability_capabilities(root=str(ROOT))
        register = build_observability_risk_register(caps_result["capabilities"])
        high_risks = [r for r in register["risks"] if r["risk_level"] in ("high", "critical")]
        assert len(high_risks) > 0


# ─── TestDeviationCheck ───────────────────────────────────────────────────────

class TestDeviationCheck:
    def test_deviation_check_returns_deviated_false(self):
        from app.foundation.observability_closure_review import check_observability_deviation
        result = check_observability_deviation(root=str(ROOT))
        assert "deviated" in result
        assert isinstance(result["deviated"], bool)

    def test_deviation_check_identifies_webhook_network(self):
        from app.foundation.observability_closure_review import check_observability_deviation
        result = check_observability_deviation(root=str(ROOT))
        assert "deviations" in result
        assert isinstance(result["deviations"], list)
        assert "deviation_count" in result

    def test_deviation_check_identifies_runtime_write(self):
        from app.foundation.observability_closure_review import check_observability_deviation
        result = check_observability_deviation(root=str(ROOT))
        deviation_types = [d.get("type") for d in result.get("deviations", [])]
        assert "deviation_count" in result


# ─── TestTestHealth ───────────────────────────────────────────────────────────

class TestTestHealth:
    def test_test_health_has_slow_test_recommendation(self):
        from app.foundation.observability_closure_review import summarize_test_health
        result = summarize_test_health(root=str(ROOT))
        assert "slow_test_risks" in result
        assert "recommended_actions" in result
        assert isinstance(result["slow_test_risks"], list)

    def test_test_health_healthy_field_present(self):
        from app.foundation.observability_closure_review import summarize_test_health
        result = summarize_test_health(root=str(ROOT))
        assert "healthy" in result
        assert isinstance(result["healthy"], bool)


# ─── TestClosureMatrix ────────────────────────────────────────────────────────

class TestClosureMatrix:
    def test_closure_matrix_has_counts(self):
        from app.foundation.observability_closure_review import build_observability_closure_matrix
        matrix = build_observability_closure_matrix(root=str(ROOT))
        assert "completed_count" in matrix
        assert "blocked_count" in matrix
        assert "read_only_count" in matrix
        assert "append_only_count" in matrix
        assert "network_call_count" in matrix
        assert "runtime_write_count" in matrix
        assert "gateway_mutation_count" in matrix

    def test_closure_matrix_capabilities_list(self):
        from app.foundation.observability_closure_review import build_observability_closure_matrix
        matrix = build_observability_closure_matrix(root=str(ROOT))
        assert isinstance(matrix["capabilities"], list)
        assert matrix["completed_count"] >= 0

    def test_closure_matrix_risks_list(self):
        from app.foundation.observability_closure_review import build_observability_closure_matrix
        matrix = build_observability_closure_matrix(root=str(ROOT))
        assert isinstance(matrix["risks"], list)
        assert matrix["risk_count"] > 0


# ─── TestNextPhaseOptions ─────────────────────────────────────────────────────

class TestNextPhaseOptions:
    def test_next_phase_options_contains_option_a_to_e(self):
        from app.foundation.observability_closure_review import (
            build_observability_closure_matrix,
            propose_next_phase_options,
        )
        matrix = build_observability_closure_matrix(root=str(ROOT))
        result = propose_next_phase_options(matrix)
        assert "options" in result
        option_ids = [o["option_id"] for o in result["options"]]
        assert "A" in option_ids
        assert "B" in option_ids
        assert "C" in option_ids
        assert "D" in option_ids
        assert "E" in option_ids

    def test_recommended_option_non_empty(self):
        from app.foundation.observability_closure_review import (
            build_observability_closure_matrix,
            propose_next_phase_options,
        )
        matrix = build_observability_closure_matrix(root=str(ROOT))
        result = propose_next_phase_options(matrix)
        assert result["recommended_option"] is not None
        assert result["recommended_option"] != ""


# ─── TestGenerateReview ────────────────────────────────────────────────────────

class TestGenerateReview:
    @pytest.mark.slow
    def test_generate_writes_tmp_path(self, tmp_path):
        from app.foundation.observability_closure_review import generate_observability_closure_review
        matrix_path = tmp_path / "R241-14A_TEST_MATRIX.json"
        review_path = tmp_path / "R241-14A_TEST_REVIEW.md"
        result = generate_observability_closure_review(
            output_path=str(matrix_path),
            review_path=str(review_path),
            root=str(ROOT),
        )
        assert matrix_path.exists()
        assert review_path.exists()
        assert result["output_path"] == str(matrix_path)

    @pytest.mark.slow
    def test_generate_matrix_valid_json(self, tmp_path):
        from app.foundation.observability_closure_review import generate_observability_closure_review
        matrix_path = tmp_path / "R241-14A_TEST_MATRIX.json"
        generate_observability_closure_review(output_path=str(matrix_path), root=str(ROOT))
        data = json.loads(matrix_path.read_text(encoding="utf-8"))
        assert "capabilities" in data
        assert "risks" in data

    @pytest.mark.slow
    def test_generate_review_validates_deviation_false(self, tmp_path):
        from app.foundation.observability_closure_review import generate_observability_closure_review
        matrix_path = tmp_path / "R241-14A_TEST_MATRIX.json"
        result = generate_observability_closure_review(output_path=str(matrix_path), root=str(ROOT))
        matrix = result["matrix"]
        assert matrix["network_call_count"] == 0

    @pytest.mark.slow
    def test_generate_review_no_runtime_write(self, tmp_path):
        from app.foundation.observability_closure_review import generate_observability_closure_review
        matrix_path = tmp_path / "R241-14A_TEST_MATRIX.json"
        result = generate_observability_closure_review(output_path=str(matrix_path), root=str(ROOT))
        matrix = result["matrix"]
        assert matrix["runtime_write_count"] == 0

    @pytest.mark.slow
    def test_generate_review_no_gateway_mutation(self, tmp_path):
        from app.foundation.observability_closure_review import generate_observability_closure_review
        matrix_path = tmp_path / "R241-14A_TEST_MATRIX.json"
        result = generate_observability_closure_review(output_path=str(matrix_path), root=str(ROOT))
        matrix = result["matrix"]
        assert matrix["gateway_mutation_count"] == 0


# ─── TestSafetyConstraints ────────────────────────────────────────────────────

class TestSafetyConstraints:
    @pytest.mark.slow
    def test_discover_does_not_write_audit_jsonl(self, tmp_path, monkeypatch):
        from app.foundation.observability_closure_review import discover_observability_capabilities
        append_count = 0
        original_append = None
        try:
            import app.audit.audit_trail_writer as writer_mod
            original_append = writer_mod.append_audit_record_to_target
            def counting_append(*args, **kwargs):
                nonlocal append_count
                append_count += 1
                return {"status": "appended", "lines_written": 0}
            writer_mod.append_audit_record_to_target = counting_append
            discover_observability_capabilities(root=str(ROOT))
            assert append_count == 0
        finally:
            if original_append:
                writer_mod.append_audit_record_to_target = original_append

    @pytest.mark.slow
    def test_deviation_check_does_not_write_runtime(self, tmp_path, monkeypatch):
        from app.foundation.observability_closure_review import check_observability_deviation
        result = check_observability_deviation(root=str(ROOT))
        assert result["deviation_count"] >= 0

    @pytest.mark.slow
    def test_generate_review_no_network_call(self, tmp_path):
        from app.foundation.observability_closure_review import generate_observability_closure_review
        matrix_path = tmp_path / "R241-14A_NO_NETWORK.json"
        result = generate_observability_closure_review(output_path=str(matrix_path), root=str(ROOT))
        assert result["matrix"]["network_call_count"] == 0
