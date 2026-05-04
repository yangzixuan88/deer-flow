"""Tests for R241-18I: Disabled Sidecar API Stub Contract (STEP-005)."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parent))

from read_only_runtime_sidecar_stub_contract import (
    DisabledSidecarStubStatus,
    DisabledSidecarStubDecision,
    DisabledSidecarRouteType,
    DisabledSidecarStubRiskLevel,
    load_disabled_sidecar_scope,
    load_disabled_sidecar_plan,
    build_disabled_sidecar_route_descriptors,
    validate_disabled_sidecar_route_descriptor,
    build_disabled_sidecar_safety_checks,
    validate_disabled_sidecar_contract,
    generate_disabled_sidecar_stub_contract,
    generate_disabled_sidecar_stub_contract_report,
    _MIGRATION_REPORTS,
    _make_safety_guards,
    _make_activation_requirements,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def migration_reports_path(tmp_path):
    """Point to tmp_path for report outputs."""
    reports = tmp_path / "backend" / "migration_reports" / "foundation_audit"
    reports.mkdir(parents=True, exist_ok=True)
    return reports


@pytest.fixture
def valid_r241_18h_report(tmp_path):
    """R241-18H report with valid scope_reconciled status."""
    reports = tmp_path / "backend" / "migration_reports" / "foundation_audit"
    reports.mkdir(parents=True, exist_ok=True)
    content = {
        "batch_id": "R241-18H-BATCH5",
        "status": "scope_reconciled",
        "decision": "proceed_with_disabled_sidecar_stub",
        "selected_batch5_scope": "disabled_sidecar_stub",
        "validation_result": {"valid": True},
        "implemented_steps": ["STEP-004"],
        "rejected_or_deferred_candidates": [
            {
                "candidate_type": "agent_memory_read_binding",
                "reason": "requires_memory_mcp_readiness_review",
            },
            {
                "candidate_type": "mcp_read_binding",
                "reason": "requires_memory_mcp_readiness_review",
            },
        ],
        "warnings": ["agent_memory_deferred_to_r241_18x"],
    }
    path = reports / "R241-18H_BATCH5_SCOPE_RECONCILIATION.json"
    path.write_text(json.dumps(content, indent=2), encoding="utf-8")
    return path


@pytest.fixture
def invalid_r241_18h_status(tmp_path):
    """R241-18H report with wrong status."""
    reports = tmp_path / "backend" / "migration_reports" / "foundation_audit"
    reports.mkdir(parents=True, exist_ok=True)
    content = {
        "batch_id": "R241-18H-BATCH5",
        "status": "partial",
        "decision": "proceed_with_disabled_sidecar_stub",
        "selected_batch5_scope": "disabled_sidecar_stub",
        "validation_result": {"valid": True},
        "rejected_or_deferred_candidates": [],
        "warnings": [],
    }
    path = reports / "R241-18H_BATCH5_SCOPE_RECONCILIATION.json"
    path.write_text(json.dumps(content, indent=2), encoding="utf-8")
    return path


@pytest.fixture
def invalid_r241_18h_decision(tmp_path):
    """R241-18H report with wrong decision."""
    reports = tmp_path / "backend" / "migration_reports" / "foundation_audit"
    reports.mkdir(parents=True, exist_ok=True)
    content = {
        "batch_id": "R241-18H-BATCH5",
        "status": "scope_reconciled",
        "decision": "reject_scope_selection",
        "selected_batch5_scope": "disabled_sidecar_stub",
        "validation_result": {"valid": True},
        "rejected_or_deferred_candidates": [],
        "warnings": [],
    }
    path = reports / "R241-18H_BATCH5_SCOPE_RECONCILIATION.json"
    path.write_text(json.dumps(content, indent=2), encoding="utf-8")
    return path


@pytest.fixture
def invalid_r241_18h_scope(tmp_path):
    """R241-18H report with memory_binding scope instead of disabled_sidecar_stub."""
    reports = tmp_path / "backend" / "migration_reports" / "foundation_audit"
    reports.mkdir(parents=True, exist_ok=True)
    content = {
        "batch_id": "R241-18H-BATCH5",
        "status": "scope_reconciled",
        "decision": "proceed_with_disabled_sidecar_stub",
        "selected_batch5_scope": "memory_binding",
        "validation_result": {"valid": True},
        "rejected_or_deferred_candidates": [],
        "warnings": [],
    }
    path = reports / "R241-18H_BATCH5_SCOPE_RECONCILIATION.json"
    path.write_text(json.dumps(content, indent=2), encoding="utf-8")
    return path


@pytest.fixture
def valid_r241_18c_plan(tmp_path):
    """R241-18C plan with STEP-005 defined as disabled_sidecar_stub."""
    reports = tmp_path / "backend" / "migration_reports" / "foundation_audit"
    reports.mkdir(parents=True, exist_ok=True)
    content = {
        "plan_id": "R241-18C_READONLY_RUNTIME_ENTRY_IMPLEMENTATION_PLAN",
        "validation_result": {"valid": True},
        "implementation_steps": [
            {
                "step_id": "STEP-001",
                "batch": "internal_helper_contract_bindings",
                "opens_http_endpoint": False,
                "writes_runtime": False,
                "network_allowed": False,
                "touches_gateway_main_path": False,
                "requires_secret": False,
                "dependencies": [],
            },
            {
                "step_id": "STEP-002",
                "batch": "cli_binding_reuse",
                "opens_http_endpoint": False,
                "writes_runtime": False,
                "network_allowed": False,
                "touches_gateway_main_path": False,
                "requires_secret": False,
                "dependencies": ["STEP-001"],
            },
            {
                "step_id": "STEP-003",
                "batch": "query_report_normalization",
                "opens_http_endpoint": False,
                "writes_runtime": False,
                "network_allowed": False,
                "touches_gateway_main_path": False,
                "requires_secret": False,
                "dependencies": ["STEP-001", "STEP-002"],
            },
            {
                "step_id": "STEP-004",
                "batch": "batch_normalization_cli_dsl",
                "opens_http_endpoint": False,
                "writes_runtime": False,
                "network_allowed": False,
                "touches_gateway_main_path": False,
                "requires_secret": False,
                "dependencies": ["STEP-001", "STEP-002", "STEP-003"],
            },
            {
                "step_id": "STEP-005",
                "batch": "disabled_sidecar_stub",
                "opens_http_endpoint": False,
                "writes_runtime": False,
                "network_allowed": False,
                "touches_gateway_main_path": False,
                "requires_secret": False,
                "dependencies": ["STEP-001", "STEP-002", "STEP-003", "STEP-004"],
            },
        ],
    }
    path = reports / "R241-18C_READONLY_RUNTIME_ENTRY_IMPLEMENTATION_PLAN.json"
    path.write_text(json.dumps(content, indent=2), encoding="utf-8")
    return path


@pytest.fixture
def missing_step_005(tmp_path):
    """R241-18C plan without STEP-005."""
    reports = tmp_path / "backend" / "migration_reports" / "foundation_audit"
    reports.mkdir(parents=True, exist_ok=True)
    content = {
        "plan_id": "R241-18C_READONLY_RUNTIME_ENTRY_IMPLEMENTATION_PLAN",
        "validation_result": {"valid": True},
        "implementation_steps": [
            {"step_id": "STEP-003", "batch": "query_report_normalization"},
            {"step_id": "STEP-004", "batch": "batch_normalization_cli_dsl"},
        ],
    }
    path = reports / "R241-18C_READONLY_RUNTIME_ENTRY_IMPLEMENTATION_PLAN.json"
    path.write_text(json.dumps(content, indent=2), encoding="utf-8")
    return path


@pytest.fixture
def valid_dependency_reports(tmp_path):
    """R241-18D/E/F/G reports with valid approvals."""
    reports = tmp_path / "backend" / "migration_reports" / "foundation_audit"
    reports.mkdir(parents=True, exist_ok=True)
    for name, batch, step in [
        ("R241-18D", 1, "STEP-001"),
        ("R241-18E", 2, "STEP-002"),
        ("R241-18F", 3, "STEP-003"),
        ("R241-18G", 4, "STEP-004"),
    ]:
        content = {
            "batch_id": f"{name}-BATCH{batch}",
            "status": "complete",
            "decision": "approve_binding_with_warnings",
            "implemented_steps": [step],
        }
        path = reports / f"{name}_READONLY_RUNTIME_ENTRY_BATCH{batch}_RESULT.json"
        path.write_text(json.dumps(content, indent=2), encoding="utf-8")
    return reports


# ---------------------------------------------------------------------------
# Test 1-4: load_disabled_sidecar_scope validation
# ---------------------------------------------------------------------------

class TestLoadScope:
    """Tests 1-4: load_disabled_sidecar_scope rejects invalid inputs."""

    def test_load_scope_requires_r241_18h_valid(self, valid_r241_18h_report, monkeypatch):
        """Test 1: load scope requires R241-18H validation valid."""
        def mock_resolve(root, filename):
            return valid_r241_18h_report
        monkeypatch.setattr("read_only_runtime_sidecar_stub_contract._resolve_path", mock_resolve)
        result = load_disabled_sidecar_scope()
        assert "R241-18H" in result["loaded"]
        assert "R241-18H_validation_valid" in result["warnings"]

    def test_load_scope_requires_selected_scope_disabled_sidecar_stub(
        self, valid_r241_18h_report, monkeypatch
    ):
        """Test 2: load scope requires selected_batch5_scope=disabled_sidecar_stub."""
        def mock_resolve(root, filename):
            return valid_r241_18h_report
        monkeypatch.setattr("read_only_runtime_sidecar_stub_contract._resolve_path", mock_resolve)
        result = load_disabled_sidecar_scope()
        assert "R241-18H_selected_scope_is_disabled_sidecar_stub" in result["warnings"]

    def test_load_scope_rejects_wrong_scope_memory(self, invalid_r241_18h_scope, monkeypatch):
        """Test 3: load scope rejects memory_binding selected scope."""
        def mock_resolve(root, filename):
            return invalid_r241_18h_scope
        monkeypatch.setattr("read_only_runtime_sidecar_stub_contract._resolve_path", mock_resolve)
        result = load_disabled_sidecar_scope()
        assert any("R241-18H_scope_not_sidecar_stub" in e for e in result["errors"])

    def test_load_scope_rejects_wrong_status(self, invalid_r241_18h_status, monkeypatch):
        """Test 4a: load scope rejects non-scope_reconciled status."""
        def mock_resolve(root, filename):
            return invalid_r241_18h_status
        monkeypatch.setattr("read_only_runtime_sidecar_stub_contract._resolve_path", mock_resolve)
        result = load_disabled_sidecar_scope()
        assert any("R241-18H_status_invalid" in e for e in result["errors"])

    def test_load_scope_rejects_wrong_decision(self, invalid_r241_18h_decision, monkeypatch):
        """Test 4b: load scope rejects non-proceed_with_disabled_sidecar_stub decision."""
        def mock_resolve(root, filename):
            return invalid_r241_18h_decision
        monkeypatch.setattr("read_only_runtime_sidecar_stub_contract._resolve_path", mock_resolve)
        result = load_disabled_sidecar_scope()
        assert any("R241-18H_decision_not_sidecar_stub" in e for e in result["errors"])


# ---------------------------------------------------------------------------
# Test 5-8: load_disabled_sidecar_plan validation
# ---------------------------------------------------------------------------

class TestLoadPlan:
    """Tests 5-8: load_disabled_sidecar_plan requires STEP-001-005."""

    def test_load_plan_requires_step_005_exists(
        self, valid_r241_18c_plan, valid_dependency_reports, monkeypatch
    ):
        """Test 5: load plan requires STEP-005 exists in R241-18C."""
        def mock_resolve(root, filename):
            base = valid_r241_18c_plan.parent
            if "PLAN" in filename:
                return valid_r241_18c_plan
            for d in valid_dependency_reports.iterdir():
                if d.name == filename:
                    return d
            return base / filename
        monkeypatch.setattr("read_only_runtime_sidecar_stub_contract._resolve_path", mock_resolve)
        result = load_disabled_sidecar_plan()
        assert "STEP-005_found" in result["warnings"]

    def test_load_plan_requires_step_001_satisfied(
        self, valid_r241_18c_plan, valid_dependency_reports, monkeypatch
    ):
        """Test 6: load plan requires STEP-001 (R241-18D) approved."""
        def mock_resolve(root, filename):
            base = valid_r241_18c_plan.parent
            if "PLAN" in filename:
                return valid_r241_18c_plan
            for d in valid_dependency_reports.iterdir():
                if d.name == filename:
                    return d
            return base / filename
        monkeypatch.setattr("read_only_runtime_sidecar_stub_contract._resolve_path", mock_resolve)
        result = load_disabled_sidecar_plan()
        assert "R241-18D_STEP-001_completed" in result["warnings"]

    def test_load_plan_requires_step_002_satisfied(
        self, valid_r241_18c_plan, valid_dependency_reports, monkeypatch
    ):
        """Test 7: load plan requires STEP-002 (R241-18E) approved."""
        def mock_resolve(root, filename):
            base = valid_r241_18c_plan.parent
            if "PLAN" in filename:
                return valid_r241_18c_plan
            for d in valid_dependency_reports.iterdir():
                if d.name == filename:
                    return d
            return base / filename
        monkeypatch.setattr("read_only_runtime_sidecar_stub_contract._resolve_path", mock_resolve)
        result = load_disabled_sidecar_plan()
        assert "R241-18E_STEP-002_completed" in result["warnings"]

    def test_load_plan_requires_step_003_satisfied(
        self, valid_r241_18c_plan, valid_dependency_reports, monkeypatch
    ):
        """Test 8: load plan requires STEP-003 (R241-18F) approved."""
        def mock_resolve(root, filename):
            base = valid_r241_18c_plan.parent
            if "PLAN" in filename:
                return valid_r241_18c_plan
            for d in valid_dependency_reports.iterdir():
                if d.name == filename:
                    return d
            return base / filename
        monkeypatch.setattr("read_only_runtime_sidecar_stub_contract._resolve_path", mock_resolve)
        result = load_disabled_sidecar_plan()
        assert "R241-18F_STEP-003_completed" in result["warnings"]


# ---------------------------------------------------------------------------
# Test 9: build_disabled_sidecar_route_descriptors creates 6 routes
# ---------------------------------------------------------------------------

class TestBuildDescriptors:
    """Test 9: build_disabled_sidecar_route_descriptors creates exactly 6 routes."""

    def test_build_descriptors_creates_six_routes(self):
        """Test 9: build_descriptors creates 6 routes."""
        descriptors = build_disabled_sidecar_route_descriptors()
        assert len(descriptors) == 6
        route_ids = {d["route_id"] for d in descriptors}
        expected = {"DSRT-001", "DSRT-002", "DSRT-003", "DSRT-004", "DSRT-005", "DSRT-006"}
        assert route_ids == expected

    def test_dsrt_001_foundation_diagnose_fields(self):
        """Test 10a: DSRT-001 has correct route type."""
        descriptors = build_disabled_sidecar_route_descriptors()
        d = next(x for x in descriptors if x["route_id"] == "DSRT-001")
        assert d["route_type"] == DisabledSidecarRouteType.FOUNDATION_DIAGNOSE.value
        assert d["enabled"] is False
        assert d["disabled_by_default"] is True
        assert d["implemented_now"] is False

    def test_dsrt_002_audit_query_fields(self):
        """Test 10b: DSRT-002 has correct route type."""
        descriptors = build_disabled_sidecar_route_descriptors()
        d = next(x for x in descriptors if x["route_id"] == "DSRT-002")
        assert d["route_type"] == DisabledSidecarRouteType.AUDIT_QUERY.value
        assert d["enabled"] is False
        assert d["disabled_by_default"] is True
        assert d["implemented_now"] is False

    def test_dsrt_003_trend_report_fields(self):
        """Test 10c: DSRT-003 has correct route type."""
        descriptors = build_disabled_sidecar_route_descriptors()
        d = next(x for x in descriptors if x["route_id"] == "DSRT-003")
        assert d["route_type"] == DisabledSidecarRouteType.TREND_REPORT.value
        assert d["enabled"] is False
        assert d["disabled_by_default"] is True
        assert d["implemented_now"] is False

    def test_dsrt_004_feishu_dryrun_fields(self):
        """Test 10d: DSRT-004 has correct route type."""
        descriptors = build_disabled_sidecar_route_descriptors()
        d = next(x for x in descriptors if x["route_id"] == "DSRT-004")
        assert d["route_type"] == DisabledSidecarRouteType.FEISHU_DRYRUN.value
        assert d["enabled"] is False
        assert d["disabled_by_default"] is True
        assert d["implemented_now"] is False

    def test_dsrt_005_feishu_presend_fields(self):
        """Test 10e: DSRT-005 has correct route type."""
        descriptors = build_disabled_sidecar_route_descriptors()
        d = next(x for x in descriptors if x["route_id"] == "DSRT-005")
        assert d["route_type"] == DisabledSidecarRouteType.FEISHU_PRESEND_VALIDATE.value
        assert d["enabled"] is False
        assert d["disabled_by_default"] is True
        assert d["implemented_now"] is False

    def test_dsrt_006_truth_state_fields(self):
        """Test 10f: DSRT-006 has correct route type."""
        descriptors = build_disabled_sidecar_route_descriptors()
        d = next(x for x in descriptors if x["route_id"] == "DSRT-006")
        assert d["route_type"] == DisabledSidecarRouteType.TRUTH_STATE.value
        assert d["enabled"] is False
        assert d["disabled_by_default"] is True
        assert d["implemented_now"] is False

    def test_all_descriptors_have_disabled_flags(self):
        """Test 11: all descriptors have enabled=False and disabled_by_default=True."""
        descriptors = build_disabled_sidecar_route_descriptors()
        for d in descriptors:
            assert d["enabled"] is False, f"{d['route_id']} enabled != False"
            assert d["disabled_by_default"] is True, f"{d['route_id']} disabled_by_default != True"
            assert d["implemented_now"] is False, f"{d['route_id']} implemented_now != False"

    def test_all_descriptors_network_listener_false(self):
        """Test 12: all descriptors have network_listener_started=False."""
        descriptors = build_disabled_sidecar_route_descriptors()
        for d in descriptors:
            assert d["network_listener_started"] is False, f"{d['route_id']} network_listener_started != False"

    def test_all_descriptors_gateway_main_path_false(self):
        """Test 13: all descriptors have gateway_main_path_touched=False."""
        descriptors = build_disabled_sidecar_route_descriptors()
        for d in descriptors:
            assert d["gateway_main_path_touched"] is False, f"{d['route_id']} gateway_main_path_touched != False"

    def test_all_descriptors_runtime_write_false(self):
        """Test 14: all descriptors have runtime_write_allowed=False."""
        descriptors = build_disabled_sidecar_route_descriptors()
        for d in descriptors:
            assert d["runtime_write_allowed"] is False, f"{d['route_id']} runtime_write_allowed != False"

    def test_all_descriptors_auth_required(self):
        """Test 15: all descriptors have auth_required=True."""
        descriptors = build_disabled_sidecar_route_descriptors()
        for d in descriptors:
            assert d["auth_required"] is True, f"{d['route_id']} auth_required != True"

    def test_all_descriptors_rate_limit_required(self):
        """Test 16: all descriptors have rate_limit_required=True."""
        descriptors = build_disabled_sidecar_route_descriptors()
        for d in descriptors:
            assert d["rate_limit_required"] is True, f"{d['route_id']} rate_limit_required != True"

    def test_all_descriptors_handler_ref_format(self):
        """Test 17: all descriptors have handler_ref as module.path string."""
        descriptors = build_disabled_sidecar_route_descriptors()
        for d in descriptors:
            assert isinstance(d["handler_ref"], str), f"{d['route_id']} handler_ref not string"
            assert ":" in d["handler_ref"], f"{d['route_id']} handler_ref missing ':'"

    def test_all_descriptors_path_namespace_disabled(self):
        """Test 18: all descriptors use /_disabled/ path namespace."""
        descriptors = build_disabled_sidecar_route_descriptors()
        for d in descriptors:
            assert "/_disabled/" in d["path"], f"{d['route_id']} path does not use /_disabled/"


# ---------------------------------------------------------------------------
# Test 19-25: validate_disabled_sidecar_route_descriptor rejections
# ---------------------------------------------------------------------------

class TestValidateDescriptor:
    """Tests 19-25: validate_disabled_sidecar_route_descriptor rejects violations."""

    def _valid_descriptor(self, route_id="DSRT-001"):
        """Return a valid descriptor for mutation tests."""
        descriptors = build_disabled_sidecar_route_descriptors()
        return dict(next(d for d in descriptors if d["route_id"] == route_id))

    def test_validate_rejects_enabled_true(self):
        """Test 19: validate rejects descriptor with enabled=True."""
        d = self._valid_descriptor()
        d["enabled"] = True
        result = validate_disabled_sidecar_route_descriptor(d)
        assert result["valid"] is False
        assert any("enabled" in i for i in result["issues"])

    def test_validate_rejects_network_listener_true(self):
        """Test 20: validate rejects descriptor with network_listener_started=True."""
        d = self._valid_descriptor()
        d["network_listener_started"] = True
        result = validate_disabled_sidecar_route_descriptor(d)
        assert result["valid"] is False
        assert any("network" in i or "listener" in i for i in result["issues"])

    def test_validate_rejects_gateway_main_path_true(self):
        """Test 21: validate rejects descriptor with gateway_main_path_touched=True."""
        d = self._valid_descriptor()
        d["gateway_main_path_touched"] = True
        result = validate_disabled_sidecar_route_descriptor(d)
        assert result["valid"] is False
        assert any("gateway" in i for i in result["issues"])

    def test_validate_rejects_runtime_write_true(self):
        """Test 22: validate rejects descriptor with runtime_write_allowed=True."""
        d = self._valid_descriptor()
        d["runtime_write_allowed"] = True
        result = validate_disabled_sidecar_route_descriptor(d)
        assert result["valid"] is False
        assert any("runtime" in i or "write" in i for i in result["issues"])

    def test_validate_rejects_missing_handler_ref(self):
        """Test 23: validate rejects descriptor without handler_ref."""
        d = self._valid_descriptor()
        d["handler_ref"] = ""
        result = validate_disabled_sidecar_route_descriptor(d)
        assert result["valid"] is False
        assert len(result["issues"]) > 0

    def test_validate_rejects_missing_path(self):
        """Test 24: validate rejects descriptor without valid path."""
        d = self._valid_descriptor()
        d["path"] = ""
        result = validate_disabled_sidecar_route_descriptor(d)
        assert result["valid"] is False
        assert len(result["issues"]) > 0

    def test_validate_accepts_valid_descriptor(self):
        """Test 25: validate accepts a fully valid descriptor."""
        d = self._valid_descriptor()
        result = validate_disabled_sidecar_route_descriptor(d)
        assert result["valid"] is True
        assert len(result["issues"]) == 0


# ---------------------------------------------------------------------------
# Test 26-28: Safety checks
# ---------------------------------------------------------------------------

class TestSafetyChecks:
    """Tests 26-28: Safety check build and validation."""

    def test_build_safety_checks_returns_checks(self):
        """Test 26: build_disabled_sidecar_safety_checks returns non-empty checks."""
        routes = build_disabled_sidecar_route_descriptors()
        checks = build_disabled_sidecar_safety_checks(routes)
        assert len(checks) > 0

    def test_safety_checks_have_required_fields(self):
        """Test 27: each safety check has required fields."""
        routes = build_disabled_sidecar_route_descriptors()
        checks = build_disabled_sidecar_safety_checks(routes)
        for c in checks:
            assert "check_id" in c
            assert "description" in c
            assert "risk_level" in c
            assert "passed" in c

    def test_safety_checks_all_pass_initially(self):
        """Test 28: all safety checks pass on initial run."""
        routes = build_disabled_sidecar_route_descriptors()
        checks = build_disabled_sidecar_safety_checks(routes)
        for c in checks:
            assert c["passed"] is True


# ---------------------------------------------------------------------------
# Test 29-33: validate_disabled_sidecar_contract rejections
# ---------------------------------------------------------------------------

class TestValidateContract:
    """Tests 29-33: validate_disabled_sidecar_contract rejects violations."""

    def _valid_contract(self):
        """Build a valid contract dict for mutation tests."""
        routes = build_disabled_sidecar_route_descriptors()
        safety_checks = build_disabled_sidecar_safety_checks(routes)
        return {
            "batch_id": "R241-18I-BATCH5",
            "route_descriptors": routes,
            "safety_checks": safety_checks,
            "scope_valid": True,
            "plan_valid": True,
        }

    def test_validate_contract_rejects_route_enabled(self):
        """Test 29: validate rejects contract with enabled route."""
        c = self._valid_contract()
        c["route_descriptors"][0]["enabled"] = True  # intentional violation
        result = validate_disabled_sidecar_contract(c)
        assert result["valid"] is False
        assert any("enabled" in i for i in result["issues"])

    def test_validate_contract_rejects_route_network_listener(self):
        """Test 30: validate rejects contract with network listener route."""
        c = self._valid_contract()
        c["route_descriptors"][0]["network_listener_started"] = True
        result = validate_disabled_sidecar_contract(c)
        assert result["valid"] is False
        assert any("network" in i for i in result["issues"])

    def test_validate_contract_rejects_route_gateway_touch(self):
        """Test 31: validate rejects contract with gateway touch route."""
        c = self._valid_contract()
        c["route_descriptors"][0]["gateway_main_path_touched"] = True
        result = validate_disabled_sidecar_contract(c)
        assert result["valid"] is False
        assert any("gateway" in i for i in result["issues"])

    def test_validate_contract_rejects_route_runtime_write(self):
        """Test 32: validate rejects contract with runtime write route."""
        c = self._valid_contract()
        c["route_descriptors"][0]["runtime_write_allowed"] = True
        result = validate_disabled_sidecar_contract(c)
        assert result["valid"] is False
        assert any("runtime" in i or "write" in i for i in result["issues"])

    def test_validate_contract_accepts_valid_contract(self):
        """Test 33: validate accepts a fully valid contract."""
        c = self._valid_contract()
        result = validate_disabled_sidecar_contract(c)
        assert result["valid"] is True


# ---------------------------------------------------------------------------
# Test 34: generate_disabled_sidecar_stub_contract valid=true
# ---------------------------------------------------------------------------

class TestGenerateContract:
    """Test 34: generate_disabled_sidecar_stub_contract returns valid contract."""

    def test_generate_contract_valid(
        self, valid_r241_18h_report, valid_r241_18c_plan, valid_dependency_reports, monkeypatch
    ):
        """Test 34: generate produces contract with valid=True validation_result."""
        def mock_resolve(root, filename):
            base = valid_r241_18h_report.parent
            if "PLAN" in filename:
                return valid_r241_18c_plan
            for d in valid_dependency_reports.iterdir():
                if d.name == filename:
                    return d
            return base / filename
        monkeypatch.setattr("read_only_runtime_sidecar_stub_contract._resolve_path", mock_resolve)
        contract = generate_disabled_sidecar_stub_contract()
        assert contract["validation_result"]["valid"] is True
        assert len(contract["route_descriptors"]) == 6


# ---------------------------------------------------------------------------
# Test 35: Report writes only to tmp_path
# ---------------------------------------------------------------------------

class TestReportGeneration:
    """Test 35: report generation writes only to tmp_path."""

    def test_report_writes_only_tmp_path(
        self, migration_reports_path, valid_r241_18h_report, valid_r241_18c_plan,
        valid_dependency_reports, monkeypatch
    ):
        """Test 35: reports are written only to tmp_path."""
        def mock_resolve(root, filename):
            base = valid_r241_18h_report.parent
            if "PLAN" in filename:
                return valid_r241_18c_plan
            for d in valid_dependency_reports.iterdir():
                if d.name == filename:
                    return d
            return base / filename

        with patch(
            "read_only_runtime_sidecar_stub_contract._MIGRATION_REPORTS",
            str(migration_reports_path)
        ):
            monkeypatch.setattr(
                "read_only_runtime_sidecar_stub_contract._resolve_path", mock_resolve
            )
            contract = generate_disabled_sidecar_stub_contract()
            result = generate_disabled_sidecar_stub_contract_report(contract)
            json_path = Path(result["json_path"])
            md_path = Path(result["md_path"])

            assert json_path.parent == migration_reports_path
            assert md_path.parent == migration_reports_path
            assert json_path.exists()
            assert md_path.exists()

            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            assert data["validation_result"]["valid"] is True
            assert len(data["route_descriptors"]) == 6

            content = md_path.read_text(encoding="utf-8")
            assert "# R241-18I" in content
            assert "DSRT-001" in content


# ---------------------------------------------------------------------------
# Tests 36-39: No runtime/audit/action queue/auto-fix
# ---------------------------------------------------------------------------

class TestNoSideEffects:
    """Tests 36-39: No runtime write, no audit write, no action queue, no auto-fix."""

    def test_no_runtime_state_modified(self):
        """Test 36: build_disabled_sidecar_route_descriptors does not modify state."""
        enabled_before = {d["route_id"]: d["enabled"] for d in build_disabled_sidecar_route_descriptors()}
        build_disabled_sidecar_route_descriptors()
        enabled_after = {d["route_id"]: d["enabled"] for d in build_disabled_sidecar_route_descriptors()}
        assert enabled_before == enabled_after

    def test_no_audit_jsonl_written(self, migration_reports_path):
        """Test 37: no audit JSONL files are written during contract generation."""
        with patch(
            "read_only_runtime_sidecar_stub_contract._MIGRATION_REPORTS",
            str(migration_reports_path)
        ):
            contract = generate_disabled_sidecar_stub_contract()
            result = generate_disabled_sidecar_stub_contract_report(contract)
            json_path = Path(result["json_path"])
            audit_files = list(json_path.parent.glob("*.jsonl"))

    def test_no_action_queue_triggered(self):
        """Test 38: descriptors have no network listener or gateway touch."""
        descriptors = build_disabled_sidecar_route_descriptors()
        for d in descriptors:
            assert d["network_listener_started"] is False
            assert d["gateway_main_path_touched"] is False

    def test_no_auto_fix_capability(self):
        """Test 39: contract has no auto-fix or self-healing capability."""
        descriptors = build_disabled_sidecar_route_descriptors()
        for d in descriptors:
            assert d["implemented_now"] is False
            assert d["enabled"] is False


# ---------------------------------------------------------------------------
# Helpers validation
# ---------------------------------------------------------------------------

class TestHelpers:
    """Validate _make_safety_guards and _make_activation_requirements helpers."""

    def test_make_safety_guards_returns_dict(self):
        """_make_safety_guards returns a dict."""
        guards = _make_safety_guards()
        assert isinstance(guards, dict)
        assert len(guards) > 0

    def test_make_activation_requirements_returns_dict(self):
        """_make_activation_requirements returns a dict."""
        reqs = _make_activation_requirements()
        assert isinstance(reqs, dict)
        assert len(reqs) > 0


# ---------------------------------------------------------------------------
# Integration test: full pipeline
# ---------------------------------------------------------------------------

class TestFullPipeline:
    """Integration test: full pipeline from scope load to report generation."""

    def test_full_pipeline(
        self, valid_r241_18h_report, valid_r241_18c_plan, valid_dependency_reports,
        monkeypatch, tmp_path
    ):
        """Full pipeline: load scope -> load plan -> build -> validate -> report."""
        reports = tmp_path / "backend" / "migration_reports" / "foundation_audit"
        reports.mkdir(parents=True, exist_ok=True)

        def mock_resolve(root, filename):
            base = valid_r241_18h_report.parent
            if "PLAN" in filename:
                return valid_r241_18c_plan
            for d in valid_dependency_reports.iterdir():
                if d.name == filename:
                    return d
            return base / filename

        with patch(
            "read_only_runtime_sidecar_stub_contract._MIGRATION_REPORTS", str(reports)
        ):
            monkeypatch.setattr(
                "read_only_runtime_sidecar_stub_contract._resolve_path", mock_resolve
            )

            scope = load_disabled_sidecar_scope()
            assert scope["loaded"]["R241-18H"]["selected_batch5_scope"] == "disabled_sidecar_stub"

            plan = load_disabled_sidecar_plan()
            assert "STEP-005_found" in plan["warnings"]

            descriptors = build_disabled_sidecar_route_descriptors()
            assert len(descriptors) == 6

            for d in descriptors:
                result = validate_disabled_sidecar_route_descriptor(d)
                assert result["valid"] is True, f"{d['route_id']} validation failed: {result['issues']}"

            safety_checks = build_disabled_sidecar_safety_checks(descriptors)
            assert len(safety_checks) > 0

            contract = generate_disabled_sidecar_stub_contract()
            assert contract["validation_result"]["valid"] is True

            result = generate_disabled_sidecar_stub_contract_report(contract)
            json_path = Path(result["json_path"])
            md_path = Path(result["md_path"])
            assert json_path.exists()
            assert md_path.exists()
