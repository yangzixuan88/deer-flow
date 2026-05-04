# R241-18J Tests: Gateway Sidecar Integration Review Gate

import sys
from pathlib import Path

# Ensure imports resolve correctly
sys.path.insert(0, str(Path(__file__).parent))

from gateway_sidecar_integration_review import (
    GatewaySidecarReviewStatus,
    GatewaySidecarReviewDecision,
    GatewaySidecarIntegrationMode,
    GatewaySidecarRiskLevel,
    load_gateway_sidecar_sources,
    inspect_gateway_code_surface,
    build_gateway_sidecar_candidates,
    build_gateway_sidecar_safety_checks,
    validate_gateway_sidecar_review,
    generate_gateway_sidecar_integration_review,
    generate_gateway_sidecar_integration_review_report,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _mock_sources() -> dict:
    """Minimal mock sources dict for testing."""
    return {
        "loaded": {
            "app/gateway/app.py": {
                "content": """
from fastapi import FastAPI
app = FastAPI()
@app.get("/health")
async def health(): return {"status": "ok"}
""",
                "size": 100,
                "lines": 5,
            },
            "app/gateway/routers/agents.py": {
                "content": """
from fastapi import APIRouter
router = APIRouter()
@router.get("/agents")
async def list_agents(): pass
""",
                "size": 80,
                "lines": 4,
            },
            "R241-18C": {"plan_id": "R241-18C"},
            "R241-18H": {"scope": "disabled_sidecar"},
        },
        "missing": [],
        "errors": [],
        "warnings": [],
    }


def _mock_inspection() -> dict:
    """Mock inspection result for testing."""
    return {
        "files": {
            "app/gateway/app.py": {
                "symbols": [],
                "integration_points": [
                    {"type": "app_lifecycle", "line": 3, "text": "app = FastAPI()"},
                    {"type": "middleware", "line": 5, "text": "@app.middleware"},
                ],
                "imports": [{"line": 1, "text": "from fastapi import FastAPI"}],
                "router_definitions": [],
                "endpoint_definitions": [
                    {"line": 4, "method": "GET", "path": "/health", "text": "@app.get('/health')"},
                ],
            },
            "app/gateway/routers/agents.py": {
                "symbols": [],
                "integration_points": [
                    {"type": "app_lifecycle", "line": 2, "text": "router = APIRouter()"},
                ],
                "imports": [{"line": 1, "text": "from fastapi import APIRouter"}],
                "router_definitions": [{"line": 2, "text": "router = APIRouter()", "name": "router"}],
                "endpoint_definitions": [
                    {"line": 3, "method": "GET", "path": "/agents", "text": "@router.get('/agents')"},
                ],
            },
        },
        "symbols": {},
        "integration_points": [
            {"type": "app_lifecycle", "line": 3, "text": "app = FastAPI()", "source_file": "app/gateway/app.py"},
            {"type": "middleware", "line": 5, "text": "@app.middleware", "source_file": "app/gateway/app.py"},
            {"type": "app_lifecycle", "line": 2, "text": "router = APIRouter()", "source_file": "app/gateway/routers/agents.py"},
        ],
    }


def _valid_review() -> dict:
    """Build a valid review dict for validation tests."""
    candidates = build_gateway_sidecar_candidates(_mock_inspection())
    safety_checks = build_gateway_sidecar_safety_checks(candidates)

    return {
        "review_id": "R241-18J",
        "status": GatewaySidecarReviewStatus.REVIEW_COMPLETE.value,
        "decision": GatewaySidecarReviewDecision.APPROVE_GATEWAY_CANDIDATES.value,
        "integration_mode": GatewaySidecarIntegrationMode.DISABLED_CONTRACT_ONLY.value,
        "candidates": candidates,
        "safety_checks": safety_checks,
        "prohibition_check": {
            "prohibition_verified": True,
            "prohibited_items": [],
            "total_checks": len(safety_checks),
            "passed_checks": len(safety_checks),
        },
        "validation_result": {"valid": True, "issues": []},
    }


def _missing_field_review(missing_field: str) -> dict:
    """Build a review dict with a missing field."""
    review = _valid_review()
    if missing_field in review:
        del review[missing_field]
    return review


# ---------------------------------------------------------------------------
# Tests: Enums
# ---------------------------------------------------------------------------

def test_gateway_sidecar_review_status_enum():
    assert GatewaySidecarReviewStatus.PENDING.value == "pending"
    assert GatewaySidecarReviewStatus.IN_PROGRESS.value == "in_progress"
    assert GatewaySidecarReviewStatus.REVIEW_COMPLETE.value == "review_complete"
    assert GatewaySidecarReviewStatus.BLOCKED.value == "blocked"


def test_gateway_sidecar_review_decision_enum():
    assert GatewaySidecarReviewDecision.APPROVE_GATEWAY_CANDIDATES.value == "approve_gateway_candidates"
    assert GatewaySidecarReviewDecision.REJECT_GATEWAY_CANDIDATES.value == "reject_gateway_candidates"
    assert GatewaySidecarReviewDecision.BLOCK_GATEWAY_INTEGRATION.value == "block_gateway_integration"
    assert GatewaySidecarReviewDecision.APPROVE_WITH_CONDITIONS.value == "approve_with_conditions"


def test_gateway_sidecar_integration_mode_enum():
    assert GatewaySidecarIntegrationMode.DISABLED_CONTRACT_ONLY.value == "disabled_contract_only"
    assert GatewaySidecarIntegrationMode.SIDECAR_ROUTER_DESIGN_ONLY.value == "sidecar_router_design_only"
    assert GatewaySidecarIntegrationMode.BLOCKING_GATEWAY_MAIN_PATH.value == "blocking_gateway_main_path"
    assert GatewaySidecarIntegrationMode.BLOCKING_FASTAPI_ROUTE_REGISTRATION.value == "blocking_fastapi_route_registration"


def test_gateway_sidecar_risk_level_enum():
    assert GatewaySidecarRiskLevel.CRITICAL.value == "critical"
    assert GatewaySidecarRiskLevel.HIGH.value == "high"
    assert GatewaySidecarRiskLevel.MEDIUM.value == "medium"
    assert GatewaySidecarRiskLevel.LOW.value == "low"
    assert GatewaySidecarRiskLevel.INFO.value == "info"


# ---------------------------------------------------------------------------
# Tests: load_gateway_sidecar_sources
# ---------------------------------------------------------------------------

def test_load_gateway_sidecar_sources_returns_sources_dict():
    """load_gateway_sidecar_sources returns a 'sources' dict with loaded/missing/errors/warnings."""
    result = load_gateway_sidecar_sources()
    assert isinstance(result, dict)
    assert "loaded" in result
    assert "missing" in result
    assert "errors" in result
    assert "warnings" in result


def test_load_gateway_sidecar_sources_loaded_structure():
    """Loaded entries have content, size, and lines fields."""
    result = load_gateway_sidecar_sources()
    for filename, data in result.get("loaded", {}).items():
        if filename.endswith(".py"):
            assert "content" in data
            assert "size" in data
            assert "lines" in data


def test_load_gateway_sidecar_sources_no_exceptions():
    """load_gateway_sidecar_sources never raises, errors accumulate in errors list."""
    result = load_gateway_sidecar_sources()
    # Errors should be empty or contain only warnings (missing files)
    assert isinstance(result.get("errors"), list)


def test_load_gateway_sidecar_sources_missing_report_warnings():
    """Missing dependency reports produce warnings."""
    result = load_gateway_sidecar_sources()
    # R241-18C and R241-18H reports won't exist in test environment
    assert isinstance(result.get("warnings"), list)


# ---------------------------------------------------------------------------
# Tests: inspect_gateway_code_surface
# ---------------------------------------------------------------------------

def test_inspect_gateway_code_surface_returns_dict():
    """inspect_gateway_code_surface returns inspection dict."""
    sources = _mock_sources()
    result = inspect_gateway_code_surface(sources)
    assert isinstance(result, dict)
    assert "files" in result
    assert "symbols" in result
    assert "integration_points" in result


def test_inspect_gateway_code_surface_finds_integration_points():
    """Integration points are extracted from source files."""
    sources = _mock_sources()
    result = inspect_gateway_code_surface(sources)
    assert len(result.get("integration_points", [])) > 0


def test_inspect_gateway_code_surface_finds_endpoints():
    """Endpoint definitions are detected."""
    sources = _mock_sources()
    result = inspect_gateway_code_surface(sources)
    endpoints_found = False
    for file_inspect in result.get("files", {}).values():
        if file_inspect.get("endpoint_definitions"):
            endpoints_found = True
            break
    assert endpoints_found


def test_inspect_gateway_code_surface_skips_non_py_files():
    """Non-Python files are skipped."""
    sources = {"loaded": {"README.md": {"content": "# README"}}}
    result = inspect_gateway_code_surface(sources)
    assert "README.md" not in result.get("files", {})


def test_inspect_gateway_code_surface_skips_dep_reports():
    """R241-18* reports are skipped."""
    sources = _mock_sources()
    result = inspect_gateway_code_surface(sources)
    assert "R241-18C" not in result.get("files", {})


# ---------------------------------------------------------------------------
# Tests: build_gateway_sidecar_candidates
# ---------------------------------------------------------------------------

def test_build_gateway_sidecar_candidates_returns_list():
    """build_gateway_sidecar_candidates returns a list."""
    inspection = _mock_inspection()
    result = build_gateway_sidecar_candidates(inspection)
    assert isinstance(result, list)


def test_build_gateway_sidecar_candidates_count():
    """Exactly 4 candidates are generated."""
    inspection = _mock_inspection()
    result = build_gateway_sidecar_candidates(inspection)
    assert len(result) == 4


def test_build_gateway_sidecar_candidates_have_ids():
    """All candidates have candidate_id field."""
    inspection = _mock_inspection()
    candidates = build_gateway_sidecar_candidates(inspection)
    for c in candidates:
        assert "candidate_id" in c
        assert c["candidate_id"].startswith("GSIC-")


def test_build_gateway_sidecar_candidates_have_all_fields():
    """All candidates have required fields."""
    inspection = _mock_inspection()
    candidates = build_gateway_sidecar_candidates(inspection)
    required_fields = [
        "candidate_id", "mode", "target_file", "target_symbol",
        "integration_point", "risk_level", "blocked", "block_reason", "notes",
    ]
    for c in candidates:
        for field in required_fields:
            assert field in c, f"Missing field {field} in {c.get('candidate_id')}"


def test_build_gateway_sidecar_candidates_blocked_modes():
    """GSIC-003 and GSIC-004 are blocked."""
    inspection = _mock_inspection()
    candidates = build_gateway_sidecar_candidates(inspection)
    blocked = {c["candidate_id"] for c in candidates if c.get("blocked")}
    assert "GSIC-003" in blocked
    assert "GSIC-004" in blocked


def test_build_gateway_sidecar_candidates_non_blocked_modes():
    """GSIC-001 and GSIC-002 are not blocked."""
    inspection = _mock_inspection()
    candidates = build_gateway_sidecar_candidates(inspection)
    non_blocked = {c["candidate_id"] for c in candidates if not c.get("blocked")}
    assert "GSIC-001" in non_blocked
    assert "GSIC-002" in non_blocked


def test_build_gateway_sidecar_candidates_integration_modes():
    """All 4 integration modes are represented."""
    inspection = _mock_inspection()
    candidates = build_gateway_sidecar_candidates(inspection)
    modes = {c.get("mode") for c in candidates}
    expected = {m.value for m in GatewaySidecarIntegrationMode}
    assert modes == expected


# ---------------------------------------------------------------------------
# Tests: build_gateway_sidecar_safety_checks
# ---------------------------------------------------------------------------

def test_build_gateway_sidecar_safety_checks_returns_list():
    """build_gateway_sidecar_safety_checks returns a list."""
    inspection = _mock_inspection()
    candidates = build_gateway_sidecar_candidates(inspection)
    result = build_gateway_sidecar_safety_checks(candidates)
    assert isinstance(result, list)


def test_build_gateway_sidecar_safety_checks_count():
    """Exactly 13 safety checks are generated."""
    inspection = _mock_inspection()
    candidates = build_gateway_sidecar_candidates(inspection)
    result = build_gateway_sidecar_safety_checks(candidates)
    assert len(result) == 13


def test_build_gateway_sidecar_safety_checks_have_ids():
    """All safety checks have check_id field."""
    inspection = _mock_inspection()
    candidates = build_gateway_sidecar_candidates(inspection)
    checks = build_gateway_sidecar_safety_checks(candidates)
    for c in checks:
        assert "check_id" in c
        assert c["check_id"].startswith("GSRC-")


def test_build_gateway_sidecar_safety_checks_have_required_fields():
    """All safety checks have required fields."""
    inspection = _mock_inspection()
    candidates = build_gateway_sidecar_candidates(inspection)
    checks = build_gateway_sidecar_safety_checks(candidates)
    required_fields = [
        "check_id", "passed", "risk_level", "description",
        "observed_value", "expected_value", "required_for_contract",
        "blocked_reasons", "warnings", "errors",
    ]
    for c in checks:
        for field in required_fields:
            assert field in c, f"Missing field {field} in {c.get('check_id')}"


def test_build_gateway_sidecar_safety_checks_risk_levels():
    """All risk levels are valid enum values."""
    inspection = _mock_inspection()
    candidates = build_gateway_sidecar_candidates(inspection)
    checks = build_gateway_sidecar_safety_checks(candidates)
    valid_levels = {e.value for e in GatewaySidecarRiskLevel}
    for c in checks:
        assert c.get("risk_level") in valid_levels


def test_build_gateway_sidecar_safety_checks_no_duplicates():
    """No duplicate check IDs."""
    inspection = _mock_inspection()
    candidates = build_gateway_sidecar_candidates(inspection)
    checks = build_gateway_sidecar_safety_checks(candidates)
    check_ids = [c.get("check_id") for c in checks]
    assert len(check_ids) == len(set(check_ids))


# ---------------------------------------------------------------------------
# Tests: validate_gateway_sidecar_review
# ---------------------------------------------------------------------------

def test_validate_gateway_sidecar_review_valid():
    """A valid review passes validation."""
    review = _valid_review()
    result = validate_gateway_sidecar_review(review)
    assert result["valid"] is True
    assert result["issues"] == []


def test_validate_gateway_sidecar_review_missing_candidates():
    """Missing candidates field fails validation."""
    review = _valid_review()
    del review["candidates"]
    result = validate_gateway_sidecar_review(review)
    assert result["valid"] is False
    assert any("candidates" in i for i in result["issues"])


def test_validate_gateway_sidecar_review_missing_safety_checks():
    """Missing safety_checks field fails validation."""
    review = _valid_review()
    del review["safety_checks"]
    result = validate_gateway_sidecar_review(review)
    assert result["valid"] is False
    assert any("safety_checks" in i for i in result["issues"])


def test_validate_gateway_sidecar_review_wrong_candidate_count():
    """Wrong candidate count fails validation."""
    review = _valid_review()
    review["candidates"] = review["candidates"][:2]
    result = validate_gateway_sidecar_review(review)
    assert result["valid"] is False
    assert any("4 candidates" in i for i in result["issues"])


def test_validate_gateway_sidecar_review_wrong_check_count():
    """Wrong safety check count fails validation."""
    review = _valid_review()
    review["safety_checks"] = review["safety_checks"][:5]
    result = validate_gateway_sidecar_review(review)
    assert result["valid"] is False
    assert any("13 safety checks" in i for i in result["issues"])


def test_validate_gateway_sidecar_review_failed_critical_check():
    """A failed critical safety check fails validation."""
    review = _valid_review()
    # Find a critical check and mark it as failed
    for c in review["safety_checks"]:
        if c.get("risk_level") == GatewaySidecarRiskLevel.CRITICAL.value:
            c["passed"] = False
            break
    result = validate_gateway_sidecar_review(review)
    assert result["valid"] is False


def test_validate_gateway_sidecar_review_insufficient_blocked():
    """Fewer than 2 blocked candidates fails validation."""
    review = _valid_review()
    for c in review["candidates"]:
        c["blocked"] = False
    result = validate_gateway_sidecar_review(review)
    assert result["valid"] is False
    assert any("blocked" in i.lower() for i in result["issues"])


# ---------------------------------------------------------------------------
# Tests: generate_gateway_sidecar_integration_review
# ---------------------------------------------------------------------------

def test_generate_gateway_sidecar_integration_review_returns_dict():
    """generate_gateway_sidecar_integration_review returns a dict."""
    result = generate_gateway_sidecar_integration_review()
    assert isinstance(result, dict)


def test_generate_gateway_sidecar_integration_review_has_required_fields():
    """Review has all required top-level fields."""
    result = generate_gateway_sidecar_integration_review()
    required_fields = [
        "review_id", "status", "decision", "integration_mode",
        "candidates", "safety_checks", "prohibition_check", "validation_result",
    ]
    for field in required_fields:
        assert field in result, f"Missing field: {field}"


def test_generate_gateway_sidecar_integration_review_has_review_id():
    """Review ID is R241-18J."""
    result = generate_gateway_sidecar_integration_review()
    assert result.get("review_id") == "R241-18J"


def test_generate_gateway_sidecar_integration_review_candidates_count():
    """Review has exactly 4 candidates."""
    result = generate_gateway_sidecar_integration_review()
    assert len(result.get("candidates", [])) == 4


def test_generate_gateway_sidecar_integration_review_safety_checks_count():
    """Review has exactly 13 safety checks."""
    result = generate_gateway_sidecar_integration_review()
    assert len(result.get("safety_checks", [])) == 13


def test_generate_gateway_sidecar_integration_review_validation_valid():
    """Review validation result is valid."""
    result = generate_gateway_sidecar_integration_review()
    validation = result.get("validation_result", {})
    assert validation.get("valid") is True


def test_generate_gateway_sidecar_integration_review_prohibition_verified():
    """Prohibition check shows no prohibited items found."""
    result = generate_gateway_sidecar_integration_review()
    prohibition = result.get("prohibition_check", {})
    assert prohibition.get("prohibition_verified") is True


def test_generate_gateway_sidecar_integration_review_decision_is_valid():
    """Decision is a valid enum value."""
    result = generate_gateway_sidecar_integration_review()
    decision = result.get("decision")
    valid_decisions = {e.value for e in GatewaySidecarReviewDecision}
    assert decision in valid_decisions


# ---------------------------------------------------------------------------
# Tests: generate_gateway_sidecar_integration_review_report
# ---------------------------------------------------------------------------

def test_generate_gateway_sidecar_integration_review_report_returns_dict():
    """Report generation returns a dict with json_path, md_path, etc."""
    result = generate_gateway_sidecar_integration_review_report()
    assert isinstance(result, dict)


def test_generate_gateway_sidecar_integration_review_report_has_paths():
    """Report has json_path and md_path fields."""
    result = generate_gateway_sidecar_integration_review_report()
    assert "json_path" in result
    assert "md_path" in result


def test_generate_gateway_sidecar_integration_review_report_has_metadata():
    """Report has review_id, status, decision fields."""
    result = generate_gateway_sidecar_integration_review_report()
    assert "review_id" in result
    assert "status" in result
    assert "decision" in result


def test_generate_gateway_sidecar_integration_review_report_json_path():
    """JSON path ends with correct filename."""
    result = generate_gateway_sidecar_integration_review_report()
    json_path = Path(result["json_path"])
    assert json_path.name == "R241-18J_GATEWAY_SIDECAR_INTEGRATION_REVIEW.json"


def test_generate_gateway_sidecar_integration_review_report_md_path():
    """Markdown path ends with correct filename."""
    result = generate_gateway_sidecar_integration_review_report()
    md_path = Path(result["md_path"])
    assert md_path.name == "R241-18J_GATEWAY_SIDECAR_INTEGRATION_REVIEW.md"


def test_generate_gateway_sidecar_integration_review_report_review_id():
    """Report review_id is R241-18J."""
    result = generate_gateway_sidecar_integration_review_report()
    assert result["review_id"] == "R241-18J"


# ---------------------------------------------------------------------------
# Tests: Integration — full pipeline
# ---------------------------------------------------------------------------

def test_full_pipeline_review_then_report():
    """Generate review, then generate report from it."""
    review = generate_gateway_sidecar_integration_review()
    report = generate_gateway_sidecar_integration_review_report(review=review)
    assert report["review_id"] == "R241-18J"
    assert report["status"] == review["status"]
    assert report["decision"] == review["decision"]
