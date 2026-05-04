"""Tests for R241-18G: Read-only Runtime Entry — Batch 4 Binding.

STEP-004: Feishu Pre-send Validate-only Entry.

Tests cover:
  - load_batch4_implementation_plan (plan validation + dependency checks)
  - inspect_r241_18f_push_deviation (push deviation recording)
  - run_feishu_presend_validate_only (binding wrapper)
  - validate_feishu_presend_result (schema validation)
  - build_batch4_safety_checks (21 safety checks)
  - validate_batch4_binding_result (batch-level validation)
  - generate_batch4_binding_result (full smoke test)
  - generate_batch4_binding_report (report generation)
  - _error_feishu_binding (error result factory)
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from backend.app.foundation.read_only_runtime_entry_batch4 import (
    ReadOnlyRuntimeBatch4BindingType,
    ReadOnlyRuntimeBatch4Decision,
    ReadOnlyRuntimeBatch4RiskLevel,
    ReadOnlyRuntimeBatch4Status,
    _build_preview_from_payload,
    _dedupe,
    _error_feishu_binding,
    _is_structured_error,
    build_batch4_safety_checks,
    generate_batch4_binding_report,
    generate_batch4_binding_result,
    inspect_r241_18f_push_deviation,
    load_batch4_implementation_plan,
    resolve_foundation_audit_report_path,
    run_feishu_presend_validate_only,
    validate_batch4_binding_result,
    validate_feishu_presend_result,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def minimal_r241_18c_plan(tmp_path: Path) -> Path:
    """Minimal R241-18C plan with STEP-004 defined."""
    plan = {
        "plan_id": "R241-18C",
        "status": "plan_ready",
        "decision": "approve_implementation_plan",
        "validation_result": {"valid": True},
        "implementation_steps": [
            {
                "step_id": "STEP-001",
                "batch": "internal_helper_binding",
                "surface_ids": ["SPEC-001"],
                "writes_runtime": False,
                "network_allowed": False,
                "opens_http_endpoint": False,
                "touches_gateway_main_path": False,
                "requires_secret": False,
                "dependencies": [],
            },
            {
                "step_id": "STEP-002",
                "batch": "cli_binding_reuse",
                "surface_ids": ["SPEC-002"],
                "writes_runtime": False,
                "network_allowed": False,
                "opens_http_endpoint": False,
                "touches_gateway_main_path": False,
                "requires_secret": False,
                "dependencies": ["STEP-001"],
            },
            {
                "step_id": "STEP-003",
                "batch": "query_report_entry",
                "surface_ids": ["SPEC-003"],
                "writes_runtime": False,
                "network_allowed": False,
                "opens_http_endpoint": False,
                "touches_gateway_main_path": False,
                "requires_secret": False,
                "dependencies": ["STEP-001", "STEP-002"],
            },
            {
                "step_id": "STEP-004",
                "batch": "feishu_dryrun_validate",
                "surface_ids": ["SPEC-005"],
                "name": "Feishu Pre-send Validate-only Entry",
                "writes_runtime": False,
                "network_allowed": False,
                "opens_http_endpoint": False,
                "touches_gateway_main_path": False,
                "requires_secret": False,
                "dependencies": ["STEP-002", "STEP-003"],
            },
            {
                "step_id": "STEP-005",
                "batch": "agent_memory_binding",
                "surface_ids": [],
                "writes_runtime": False,
                "network_allowed": False,
                "opens_http_endpoint": False,
                "touches_gateway_main_path": False,
                "requires_secret": False,
                "dependencies": ["STEP-001", "STEP-002", "STEP-003"],
            },
        ],
    }
    audit_dir = tmp_path / "migration_reports" / "foundation_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    plan_path = audit_dir / "R241-18C_READONLY_RUNTIME_ENTRY_IMPLEMENTATION_PLAN.json"
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return audit_dir


@pytest.fixture
def minimal_r241_18f_result(minimal_r241_18c_plan: Path) -> Path:
    """Minimal R241-18F result with STEP-003 approved. Also creates batch1 and batch2."""
    batch1 = {
        "batch_id": "R241-18D-BATCH1",
        "status": "implemented",
        "decision": "approve_batch1_binding",
        "implemented_steps": ["STEP-001"],
        "validation_result": {"valid": True},
        "binding_results": [],
        "safety_checks": [],
        "approved_binding_count": 1,
        "blocked_binding_count": 0,
    }
    batch2 = {
        "batch_id": "R241-18E-BATCH2",
        "status": "implemented",
        "decision": "approve_batch2_binding",
        "implemented_steps": ["STEP-002"],
        "validation_result": {"valid": True},
        "binding_results": [],
        "safety_checks": [],
        "approved_binding_count": 1,
        "blocked_binding_count": 0,
    }
    batch3 = {
        "batch_id": "R241-18F-BATCH3",
        "status": "implemented",
        "decision": "approve_batch3_binding",
        "implemented_steps": ["STEP-003"],
        "validation_result": {"valid": True},
        "binding_results": [],
        "safety_checks": [],
        "approved_binding_count": 1,
        "blocked_binding_count": 0,
    }
    (minimal_r241_18c_plan / "R241-18D_READONLY_RUNTIME_ENTRY_BATCH1_RESULT.json").write_text(
        json.dumps(batch1, indent=2), encoding="utf-8")
    (minimal_r241_18c_plan / "R241-18E_READONLY_RUNTIME_ENTRY_BATCH2_RESULT.json").write_text(
        json.dumps(batch2, indent=2), encoding="utf-8")
    (minimal_r241_18c_plan / "R241-18F_READONLY_RUNTIME_ENTRY_BATCH3_RESULT.json").write_text(
        json.dumps(batch3, indent=2), encoding="utf-8")
    return minimal_r241_18c_plan


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Path Resolution
# ─────────────────────────────────────────────────────────────────────────────

class TestResolvePath:
    def test_resolve_with_none_returns_canonical(self):
        path = resolve_foundation_audit_report_path()
        assert "migration_reports" in str(path)
        assert "foundation_audit" in str(path)

    def test_resolve_with_repo_root(self):
        path = resolve_foundation_audit_report_path("E:/OpenClaw-Base/deerflow")
        assert "migration_reports" in str(path)
        assert "foundation_audit" in str(path)

    def test_resolve_with_backend_root(self):
        path = resolve_foundation_audit_report_path("E:/OpenClaw-Base/deerflow/backend")
        assert "migration_reports" in str(path)

    def test_resolve_with_filename(self):
        path = resolve_foundation_audit_report_path(filename="test.json")
        assert path.name == "test.json"

    def test_resolve_inside_canonical_dir(self):
        canonical = resolve_foundation_audit_report_path()
        sub = canonical / "subdir"
        resolved = resolve_foundation_audit_report_path(str(sub))
        assert resolved == sub


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Enums
# ─────────────────────────────────────────────────────────────────────────────

class TestBatch4Enums:
    def test_status_values(self):
        assert ReadOnlyRuntimeBatch4Status.IMPLEMENTED.value == "implemented"
        assert ReadOnlyRuntimeBatch4Status.BLOCKED_MISSING_PLAN.value == "blocked_missing_plan"
        assert ReadOnlyRuntimeBatch4Status.BLOCKED_BATCH3_MISSING.value == "blocked_batch3_missing"

    def test_decision_values(self):
        assert ReadOnlyRuntimeBatch4Decision.APPROVE_BATCH4_BINDING.value == "approve_batch4_binding"
        assert ReadOnlyRuntimeBatch4Decision.BLOCK_BATCH4_BINDING.value == "block_batch4_binding"

    def test_binding_type_values(self):
        assert ReadOnlyRuntimeBatch4BindingType.FEISHU_PRESEND_VALIDATE_HELPER.value == "feishu_presend_validate_helper"
        assert ReadOnlyRuntimeBatch4BindingType.VALIDATION_HELPER.value == "validation_helper"

    def test_risk_level_values(self):
        assert ReadOnlyRuntimeBatch4RiskLevel.LOW.value == "low"
        assert ReadOnlyRuntimeBatch4RiskLevel.CRITICAL.value == "critical"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

class TestHelpers:
    def test_is_structured_error_true(self):
        assert _is_structured_error("invalid_window:all_available") is True

    def test_is_structured_error_false(self):
        assert _is_structured_error("something went wrong") is False

    def test_dedupe_removes_duplicates(self):
        result = _dedupe(["a", "b", "a", "c", "b"])
        assert result == ["a", "b", "c"]

    def test_dedupe_preserves_order(self):
        result = _dedupe(["x", "y", "z"])
        assert result == ["x", "y", "z"]

    def test_build_preview_from_payload_json(self):
        payload = {
            "presend_validation": {
                "status": "valid",
                "valid": True,
                "blocked_reasons": [],
                "warnings": ["foo_warning"],
            }
        }
        preview = _build_preview_from_payload(payload, "json")
        assert "status=valid" in preview
        assert "valid=True" in preview

    def test_build_preview_from_payload_empty(self):
        assert _build_preview_from_payload({}, "json") == ""
        assert _build_preview_from_payload({"presend_validation": {}}, "json") == ""


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Load Batch 4 Plan
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadBatch4Plan:
    def test_load_plan_missing_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_batch4_implementation_plan(root=str(tmp_path))

    def test_load_plan_step_004_not_found(self, minimal_r241_18f_result: Path):
        plan_path = minimal_r241_18f_result / "R241-18C_READONLY_RUNTIME_ENTRY_IMPLEMENTATION_PLAN.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan["implementation_steps"] = [
            {"step_id": "STEP-001", "batch": "x", "surface_ids": [], "writes_runtime": False,
             "network_allowed": False, "opens_http_endpoint": False,
             "touches_gateway_main_path": False, "requires_secret": False, "dependencies": []},
        ]
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        with pytest.raises(ValueError, match="STEP-004 not found"):
            load_batch4_implementation_plan(root=str(minimal_r241_18f_result))

    def test_load_plan_writes_runtime_true_raises(self, minimal_r241_18f_result: Path):
        plan_path = minimal_r241_18f_result / "R241-18C_READONLY_RUNTIME_ENTRY_IMPLEMENTATION_PLAN.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        for step in plan["implementation_steps"]:
            if step["step_id"] == "STEP-004":
                step["writes_runtime"] = True
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        with pytest.raises(ValueError, match="writes_runtime must be False"):
            load_batch4_implementation_plan(root=str(minimal_r241_18f_result))

    def test_load_plan_network_allowed_true_raises(self, minimal_r241_18f_result: Path):
        plan_path = minimal_r241_18f_result / "R241-18C_READONLY_RUNTIME_ENTRY_IMPLEMENTATION_PLAN.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        for step in plan["implementation_steps"]:
            if step["step_id"] == "STEP-004":
                step["network_allowed"] = True
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        with pytest.raises(ValueError, match="network_allowed must be False"):
            load_batch4_implementation_plan(root=str(minimal_r241_18f_result))

    def test_load_plan_wrong_batch_raises(self, minimal_r241_18f_result: Path):
        plan_path = minimal_r241_18f_result / "R241-18C_READONLY_RUNTIME_ENTRY_IMPLEMENTATION_PLAN.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        for step in plan["implementation_steps"]:
            if step["step_id"] == "STEP-004":
                step["batch"] = "wrong_batch"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        with pytest.raises(ValueError, match="feishu_dryrun_validate"):
            load_batch4_implementation_plan(root=str(minimal_r241_18f_result))

    def test_load_plan_missing_spec_005_raises(self, minimal_r241_18f_result: Path):
        plan_path = minimal_r241_18f_result / "R241-18C_READONLY_RUNTIME_ENTRY_IMPLEMENTATION_PLAN.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        for step in plan["implementation_steps"]:
            if step["step_id"] == "STEP-004":
                step["surface_ids"] = ["SPEC-001"]
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        with pytest.raises(ValueError, match="SPEC-005"):
            load_batch4_implementation_plan(root=str(minimal_r241_18f_result))

    def test_load_plan_wrong_dependencies_raises(self, minimal_r241_18f_result: Path):
        plan_path = minimal_r241_18f_result / "R241-18C_READONLY_RUNTIME_ENTRY_IMPLEMENTATION_PLAN.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        for step in plan["implementation_steps"]:
            if step["step_id"] == "STEP-004":
                step["dependencies"] = ["STEP-001"]
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        with pytest.raises(ValueError, match="STEP-002.*STEP-003"):
            load_batch4_implementation_plan(root=str(minimal_r241_18f_result))

    def test_load_plan_batch1_missing_raises(self, minimal_r241_18f_result: Path):
        # Remove batch1 result to simulate missing dependency
        batch1_path = minimal_r241_18f_result.parent.parent / "foundation_audit" / "R241-18D_READONLY_RUNTIME_ENTRY_BATCH1_RESULT.json"
        # Actually batch1 is in the same dir - remove it
        (minimal_r241_18f_result / "R241-18D_READONLY_RUNTIME_ENTRY_BATCH1_RESULT.json").unlink()
        with pytest.raises(FileNotFoundError):
            load_batch4_implementation_plan(root=str(minimal_r241_18f_result))

    def test_load_plan_batch1_step_missing_raises(self, minimal_r241_18f_result: Path):
        # Fix batch1 to have no STEP-001
        r241_18d = minimal_r241_18f_result / "R241-18D_READONLY_RUNTIME_ENTRY_BATCH1_RESULT.json"
        r241_18d.write_text(json.dumps({
            "batch_id": "R241-18D-BATCH1",
            "decision": "approve_batch1_binding",
            "implemented_steps": [],
            "validation_result": {"valid": True},
        }), encoding="utf-8")
        with pytest.raises(ValueError, match="STEP-001"):
            load_batch4_implementation_plan(root=str(minimal_r241_18f_result))

    def test_load_plan_success(self, minimal_r241_18f_result: Path):
        result = load_batch4_implementation_plan(root=str(minimal_r241_18f_result))
        assert result["plan"]["plan_id"] == "R241-18C"
        assert result["batch1_result"]["batch_id"] == "R241-18D-BATCH1"
        assert result["batch2_result"]["batch_id"] == "R241-18E-BATCH2"
        assert result["batch3_result"]["batch_id"] == "R241-18F-BATCH3"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Inspect R241-18F Push Deviation
# ─────────────────────────────────────────────────────────────────────────────

class TestInspectPushDeviation:
    def test_returns_push_deviation_recorded_true(self):
        result = inspect_r241_18f_push_deviation()
        assert result["push_deviation_recorded"] is True
        assert result["process_deviation_git_push_executed"] is True
        assert result["recorded_at"] is not None

    def test_returns_dict_with_required_keys(self):
        result = inspect_r241_18f_push_deviation()
        required_keys = [
            "head_hash", "origin_main_hash", "ahead_count",
            "push_deviation_recorded", "process_deviation_git_push_executed",
            "gh_workflow_available", "unexpected_workflow_run",
            "deviation_description", "recorded_at",
        ]
        for key in required_keys:
            assert key in result


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Run Feishu Pre-send Validate-only
# ─────────────────────────────────────────────────────────────────────────────

class TestRunFeishuPresendValidate:
    def test_invalid_window_returns_error(self):
        result = run_feishu_presend_validate_only(window="invalid_window")
        assert result["status"] == "failed"
        assert result["decision"] == "block_batch4_binding"
        assert any("invalid_window" in e for e in result["errors"])

    def test_invalid_output_format_returns_error(self):
        result = run_feishu_presend_validate_only(window="all_available", output_format="xml")
        assert result["status"] == "failed"
        assert result["decision"] == "block_batch4_binding"
        assert any("invalid_output_format" in e for e in result["errors"])

    def test_valid_call_returns_expected_binding_fields(self):
        result = run_feishu_presend_validate_only(
            window="all_available",
            output_format="json",
        )
        assert "binding_id" in result
        assert result["binding_type"] == "feishu_presend_validate_helper"
        assert result["surface_id"] == "SPEC-005"
        assert result["command"] == "audit-trend-feishu-presend"
        assert result["window"] == "all_available"
        assert result["output_format"] == "json"

    def test_valid_call_has_all_safety_fields_false(self):
        result = run_feishu_presend_validate_only(
            window="all_available",
            output_format="json",
        )
        assert result["writes_runtime"] is False
        assert result["writes_audit_jsonl"] is False
        assert result["writes_report_artifact"] is False
        assert result["opened_jsonl_write_handle"] is False
        assert result["network_used"] is False
        assert result["feishu_send_attempted"] is False
        assert result["webhook_called"] is False
        assert result["webhook_value_read"] is False
        assert result["secret_read"] is False
        assert result["scheduler_triggered"] is False
        assert result["gateway_main_path_touched"] is False

    def test_confirmation_phrase_recorded(self):
        result = run_feishu_presend_validate_only(
            window="all_available",
            output_format="json",
            confirmation_phrase="CONFIRM_FEISHU_TREND_SEND",
        )
        assert result["confirmation_phrase_provided"] is True

    def test_webhook_ref_recorded(self):
        result = run_feishu_presend_validate_only(
            window="all_available",
            output_format="json",
            webhook_ref_type="env",
            webhook_ref_name="FEISHU_WEBHOOK_URL",
        )
        assert result["webhook_ref_provided"] is True

    def test_send_allowed_false(self):
        result = run_feishu_presend_validate_only(
            window="all_available",
            output_format="json",
        )
        assert result["send_allowed"] is False

    def test_validation_valid_on_success(self):
        result = run_feishu_presend_validate_only(
            window="all_available",
            output_format="json",
        )
        assert result["validation"]["valid"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Validate Feishu Presend Result
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateFeishuPresendResult:
    def test_missing_required_field(self):
        result = run_feishu_presend_validate_only(window="all_available", output_format="json")
        del result["binding_id"]
        validation = validate_feishu_presend_result(result)
        assert validation["valid"] is False
        assert any("missing_required_field:binding_id" in e for e in validation["issues"])

    def test_writes_runtime_true_fails(self):
        result = run_feishu_presend_validate_only(window="all_available", output_format="json")
        result["writes_runtime"] = True
        validation = validate_feishu_presend_result(result)
        assert validation["valid"] is False
        assert any("writes_runtime_must_be_False" in i for i in validation["issues"])

    def test_send_allowed_true_fails(self):
        result = run_feishu_presend_validate_only(window="all_available", output_format="json")
        result["send_allowed"] = True
        validation = validate_feishu_presend_result(result)
        assert validation["valid"] is False
        assert any("send_allowed_must_be_False" in i for i in validation["issues"])

    def test_webhook_value_read_true_fails(self):
        result = run_feishu_presend_validate_only(window="all_available", output_format="json")
        result["webhook_value_read"] = True
        validation = validate_feishu_presend_result(result)
        assert validation["valid"] is False
        assert any("webhook_value_read_must_be_False" in i for i in validation["issues"])

    def test_valid_result_passes(self):
        result = run_feishu_presend_validate_only(window="all_available", output_format="json")
        validation = validate_feishu_presend_result(result)
        assert validation["valid"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Safety Checks Builder
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildBatch4SafetyChecks:
    def test_returns_21_checks(self):
        binding_results = [
            run_feishu_presend_validate_only(window="all_available", output_format="json"),
        ]
        checks = build_batch4_safety_checks(binding_results)
        assert len(checks) == 21

    def test_no_runtime_write_passed(self):
        binding_results = [
            run_feishu_presend_validate_only(window="all_available", output_format="json"),
        ]
        checks = build_batch4_safety_checks(binding_results)
        check_ids = {c["check_id"] for c in checks}
        assert "no_runtime_write" in check_ids
        no_rw = next(c for c in checks if c["check_id"] == "no_runtime_write")
        assert no_rw["passed"] is True

    def test_no_feishu_send_passed(self):
        binding_results = [
            run_feishu_presend_validate_only(window="all_available", output_format="json"),
        ]
        checks = build_batch4_safety_checks(binding_results)
        no_send = next(c for c in checks if c["check_id"] == "no_feishu_send")
        assert no_send["passed"] is True

    def test_send_allowed_false_passed(self):
        binding_results = [
            run_feishu_presend_validate_only(window="all_available", output_format="json"),
        ]
        checks = build_batch4_safety_checks(binding_results)
        send_allowed_check = next(c for c in checks if c["check_id"] == "send_allowed_false")
        assert send_allowed_check["passed"] is True

    def test_no_webhook_value_read_passed(self):
        binding_results = [
            run_feishu_presend_validate_only(window="all_available", output_format="json"),
        ]
        checks = build_batch4_safety_checks(binding_results)
        no_vr = next(c for c in checks if c["check_id"] == "no_webhook_value_read")
        assert no_vr["passed"] is True

    def test_all_batch_deps_passed(self):
        binding_results = [
            run_feishu_presend_validate_only(window="all_available", output_format="json"),
        ]
        checks = build_batch4_safety_checks(binding_results)
        dep_checks = [c for c in checks if "_dependency_satisfied" in c["check_id"]]
        assert len(dep_checks) == 3
        for dc in dep_checks:
            assert dc["passed"] is True

    def test_plan_scope_limited_passed(self):
        binding_results = [
            run_feishu_presend_validate_only(window="all_available", output_format="json"),
        ]
        checks = build_batch4_safety_checks(binding_results)
        scope = next(c for c in checks if c["check_id"] == "plan_scope_limited_to_step_004")
        assert scope["passed"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Batch Validation
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateBatch4BindingResult:
    def test_only_step_004_allowed(self):
        batch = {
            "implemented_steps": ["STEP-004"],
            "binding_results": [
                run_feishu_presend_validate_only(window="all_available", output_format="json"),
            ],
            "safety_checks": build_batch4_safety_checks([
                run_feishu_presend_validate_only(window="all_available", output_format="json"),
            ]),
            "source_batch1_ref": "R241-18D_READONLY_RUNTIME_ENTRY_BATCH1_RESULT",
            "source_batch2_ref": "R241-18E_READONLY_RUNTIME_ENTRY_BATCH2_RESULT",
            "source_batch3_ref": "R241-18F_READONLY_RUNTIME_ENTRY_BATCH3_RESULT",
            "push_deviation": {"push_deviation_recorded": True},
        }
        validation = validate_batch4_binding_result(batch)
        print("ISSUES:", validation["issues"])
        print("FAILED:", [(c["check_id"], c["required_for_batch4"]) for c in batch["safety_checks"] if not c["passed"]])
        assert validation["valid"] is True

    def test_step_005_not_allowed(self):
        batch = {
            "implemented_steps": ["STEP-004", "STEP-005"],
            "binding_results": [],
            "safety_checks": [],
            "source_batch1_ref": "",
            "source_batch2_ref": "",
            "source_batch3_ref": "",
            "push_deviation": {},
        }
        validation = validate_batch4_binding_result(batch)
        assert validation["valid"] is False
        assert any("STEP-005" in e for e in validation["issues"])

    def test_send_allowed_true_fails(self):
        r = run_feishu_presend_validate_only(window="all_available", output_format="json")
        r["send_allowed"] = True
        batch = {
            "implemented_steps": ["STEP-004"],
            "binding_results": [r],
            "safety_checks": build_batch4_safety_checks([r]),
            "source_batch1_ref": "R241-18D",
            "source_batch2_ref": "R241-18E",
            "source_batch3_ref": "R241-18F",
            "push_deviation": {"push_deviation_recorded": True},
        }
        validation = validate_batch4_binding_result(batch)
        assert validation["valid"] is False

    def test_push_deviation_not_recorded_fails(self):
        batch = {
            "implemented_steps": ["STEP-004"],
            "binding_results": [
                run_feishu_presend_validate_only(window="all_available", output_format="json"),
            ],
            "safety_checks": [],
            "source_batch1_ref": "R241-18D",
            "source_batch2_ref": "R241-18E",
            "source_batch3_ref": "R241-18F",
            "push_deviation": {"push_deviation_recorded": False},
        }
        validation = validate_batch4_binding_result(batch)
        assert validation["valid"] is False
        assert any("push_deviation" in e for e in validation["issues"])


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Error Binding Factory
# ─────────────────────────────────────────────────────────────────────────────

class TestErrorFeishuBinding:
    def test_error_binding_fields(self):
        result = _error_feishu_binding(
            binding_id="FPRS-ERR-TEST",
            window="all_available",
            output_format="json",
            exc=ValueError("test error"),
        )
        assert result["binding_id"] == "FPRS-ERR-TEST"
        assert result["binding_type"] == "feishu_presend_validate_helper"
        assert result["surface_id"] == "SPEC-005"
        assert result["status"] == "failed"
        assert result["decision"] == "block_batch4_binding"
        assert result["writes_runtime"] is False
        assert result["send_allowed"] is False
        assert "smoke_raised" in result["errors"][0]


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Generate Batch 4 Binding Result
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateBatch4BindingResult:
    def test_generate_returns_expected_batch_id(self, minimal_r241_18f_result: Path):
        result = generate_batch4_binding_result(root=str(minimal_r241_18f_result))
        assert result["batch_id"] == "R241-18G-BATCH4"

    def test_generate_implements_step_004(self, minimal_r241_18f_result: Path):
        result = generate_batch4_binding_result(root=str(minimal_r241_18f_result))
        assert "STEP-004" in result["implemented_steps"]

    def test_generate_has_push_deviation(self, minimal_r241_18f_result: Path):
        result = generate_batch4_binding_result(root=str(minimal_r241_18f_result))
        assert "push_deviation" in result
        assert result["push_deviation"]["push_deviation_recorded"] is True

    def test_generate_runs_three_bindings(self, minimal_r241_18f_result: Path):
        result = generate_batch4_binding_result(root=str(minimal_r241_18f_result))
        assert len(result["binding_results"]) == 3

    def test_generate_has_safety_checks(self, minimal_r241_18f_result: Path):
        result = generate_batch4_binding_result(root=str(minimal_r241_18f_result))
        assert len(result["safety_checks"]) >= 21

    def test_generate_batch_validation_valid(self, minimal_r241_18f_result: Path):
        result = generate_batch4_binding_result(root=str(minimal_r241_18f_result))
        assert result["validation_result"]["valid"] is True

    def test_generate_source_refs_all_present(self, minimal_r241_18f_result: Path):
        result = generate_batch4_binding_result(root=str(minimal_r241_18f_result))
        assert "R241-18C" in result["source_plan_ref"]
        assert "R241-18D" in result["source_batch1_ref"]
        assert "R241-18E" in result["source_batch2_ref"]
        assert "R241-18F" in result["source_batch3_ref"]


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Generate Batch 4 Report
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateBatch4Report:
    def test_report_generates_json_and_md(self, minimal_r241_18f_result: Path):
        with tempfile.TemporaryDirectory() as tmp:
            result = generate_batch4_binding_report(
                batch=generate_batch4_binding_result(root=str(minimal_r241_18f_result)),
                output_path=tmp,
            )
            assert Path(result["json_path"]).exists()
            assert Path(result["md_path"]).exists()

    def test_report_json_valid(self, minimal_r241_18f_result: Path):
        with tempfile.TemporaryDirectory() as tmp:
            result = generate_batch4_binding_report(
                batch=generate_batch4_binding_result(root=str(minimal_r241_18f_result)),
                output_path=tmp,
            )
            data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
            assert data["batch_id"] == "R241-18G-BATCH4"

    def test_report_md_contains_sections(self, minimal_r241_18f_result: Path):
        with tempfile.TemporaryDirectory() as tmp:
            result = generate_batch4_binding_report(
                batch=generate_batch4_binding_result(root=str(minimal_r241_18f_result)),
                output_path=tmp,
            )
            md = Path(result["md_path"]).read_text(encoding="utf-8")
            assert "# R241-18G" in md
            assert "## Binding Results" in md
            assert "## Safety Checks" in md
            assert "## Safety Summary" in md


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Round-trip validation
# ─────────────────────────────────────────────────────────────────────────────

class TestRoundTrip:
    def test_result_passes_full_validation(self, minimal_r241_18f_result: Path):
        batch = generate_batch4_binding_result(root=str(minimal_r241_18f_result))
        validation = validate_batch4_binding_result(batch)
        assert validation["valid"] is True
        assert validation["failed_safety_checks"] == 0

    def test_all_binding_results_valid_schema(self, minimal_r241_18f_result: Path):
        batch = generate_batch4_binding_result(root=str(minimal_r241_18f_result))
        for r in batch["binding_results"]:
            v = validate_feishu_presend_result(r)
            assert v["valid"] is True, f"{r['binding_id']}: {v['issues']}"
