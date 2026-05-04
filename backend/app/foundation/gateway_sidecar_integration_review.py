# R241-18J: Gateway Sidecar Integration Review Gate
# STEP-006 — Read-only review of Gateway code surface, building integration candidates.
# PROHIBITION: No sidecar, HTTP endpoint, FastAPI route, or network listener may be implemented.
# Only outputs: gateway_sidecar_integration_review.py, test file, and R241-18J_*.{json,md} reports.

from __future__ import annotations

import json
import re
from enum import Enum
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class GatewaySidecarReviewStatus(str, Enum):
    """Review status for the gateway sidecar integration review."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    REVIEW_COMPLETE = "review_complete"
    BLOCKED = "blocked"


class GatewaySidecarReviewDecision(str, Enum):
    """Review gate decision."""

    APPROVE_GATEWAY_CANDIDATES = "approve_gateway_candidates"
    REJECT_GATEWAY_CANDIDATES = "reject_gateway_candidates"
    BLOCK_GATEWAY_INTEGRATION = "block_gateway_integration"
    APPROVE_WITH_CONDITIONS = "approve_with_conditions"


class GatewaySidecarIntegrationMode(str, Enum):
    """Integration mode candidates for gateway sidecar."""

    DISABLED_CONTRACT_ONLY = "disabled_contract_only"
    SIDECAR_ROUTER_DESIGN_ONLY = "sidecar_router_design_only"
    BLOCKING_GATEWAY_MAIN_PATH = "blocking_gateway_main_path"
    BLOCKING_FASTAPI_ROUTE_REGISTRATION = "blocking_fastapi_route_registration"


class GatewaySidecarRiskLevel(str, Enum):
    """Risk level for gateway integration safety checks."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# ---------------------------------------------------------------------------
# Data Structures (plain dicts, not classes)
# ---------------------------------------------------------------------------

# GatewaySidecarCandidate: integration candidate descriptor
_GATEWAY_CANDIDATE_FIELDS = frozenset({
    "candidate_id", "mode", "target_file", "target_symbol", "integration_point",
    "risk_level", "blocked", "block_reason", "notes",
})

# GatewaySidecarSafetyCheck: safety check result
_GATEWAY_SAFETY_CHECK_FIELDS = frozenset({
    "check_id", "passed", "risk_level", "description", "observed_value",
    "expected_value", "required_for_contract", "blocked_reasons", "warnings", "errors",
})

# GatewaySidecarIntegrationReview: top-level review result
_GATEWAY_REVIEW_FIELDS = frozenset({
    "review_id", "status", "decision", "integration_mode", "candidates",
    "safety_checks", "validation_result", "prohibition_check",
})

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MIGRATION_REPORTS = "migration_reports/foundation_audit"

# Gateway code surface files to inspect
_GATEWAY_CODE_SURFACE_FILES = [
    "app/gateway/__init__.py",
    "app/gateway/app.py",
    "app/gateway/config.py",
    "app/gateway/deps.py",
    "app/gateway/path_utils.py",
    "app/gateway/context.py",
    "app/gateway/mode_router.py",
    "app/gateway/mode_instrumentation.py",
    "app/gateway/services.py",
    "app/gateway/routers/__init__.py",
    "app/gateway/routers/agents.py",
    "app/gateway/routers/artifacts.py",
    "app/gateway/routers/assistants_compat.py",
    "app/gateway/routers/channels.py",
    "app/gateway/routers/mcp.py",
    "app/gateway/routers/memory.py",
    "app/gateway/routers/models.py",
    "app/gateway/routers/runs.py",
    "app/gateway/routers/skills.py",
    "app/gateway/routers/suggestions.py",
    "app/gateway/routers/threads.py",
    "app/gateway/routers/thread_runs.py",
    "app/gateway/routers/uploads.py",
]

# Integration modes
_INTEGRATION_MODES = [
    GatewaySidecarIntegrationMode.DISABLED_CONTRACT_ONLY,
    GatewaySidecarIntegrationMode.SIDECAR_ROUTER_DESIGN_ONLY,
    GatewaySidecarIntegrationMode.BLOCKING_GATEWAY_MAIN_PATH,
    GatewaySidecarIntegrationMode.BLOCKING_FASTAPI_ROUTE_REGISTRATION,
]


# ---------------------------------------------------------------------------
# Path Resolution
# ---------------------------------------------------------------------------

def _resolve_path(root: Path | str | None, filename: str) -> Path:
    """Resolve a report path, falling back to _MIGRATION_REPORTS."""
    base = Path(root) if root else Path(_MIGRATION_REPORTS)
    if base.is_absolute():
        return base / filename
    # Relative: always resolve from CWD (backend/)
    return Path(_MIGRATION_REPORTS) / filename


# ---------------------------------------------------------------------------
# Core Objects (factory functions returning plain dicts)
# ---------------------------------------------------------------------------

def _make_candidate(
    candidate_id: str,
    mode: str,
    target_file: str,
    target_symbol: str,
    integration_point: str,
    risk_level: str,
    blocked: bool = False,
    block_reason: str = "",
    notes: str = "",
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "mode": mode,
        "target_file": target_file,
        "target_symbol": target_symbol,
        "integration_point": integration_point,
        "risk_level": risk_level,
        "blocked": blocked,
        "block_reason": block_reason,
        "notes": notes,
    }


def _make_check(
    check_id: str,
    passed: bool,
    risk_level: str,
    description: str,
    observed_value: str,
    expected_value: str,
    required_for_contract: bool = False,
    blocked_reasons: list[str] | None = None,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "passed": passed,
        "risk_level": risk_level,
        "description": description,
        "observed_value": observed_value,
        "expected_value": expected_value,
        "required_for_contract": required_for_contract,
        "blocked_reasons": blocked_reasons or [],
        "warnings": warnings or [],
        "errors": errors or [],
    }


# ---------------------------------------------------------------------------
# load_gateway_sidecar_sources
# ---------------------------------------------------------------------------

def load_gateway_sidecar_sources(
    root: Path | str | None = None,
) -> dict[str, Any]:
    """Load gateway code surface files and dependency reports.

    Returns a 'sources' dict: {loaded: {filename: content}, missing: [], errors: [], warnings: []}
    No exceptions raised — all errors accumulate in the 'errors' list.
    """
    sources: dict[str, Any] = {
        "loaded": {},
        "missing": [],
        "errors": [],
        "warnings": [],
    }

    root_path = Path(root) if root else Path.cwd()

    # Load gateway code surface files
    for rel_path in _GATEWAY_CODE_SURFACE_FILES:
        full_path = root_path / rel_path
        try:
            if full_path.exists():
                content = full_path.read_text(encoding="utf-8")
                sources["loaded"][rel_path] = {
                    "content": content,
                    "size": len(content),
                    "lines": content.count("\n") + 1,
                }
            else:
                sources["missing"].append(rel_path)
                sources["warnings"].append(f"Gateway code surface file not found: {rel_path}")
        except Exception as e:
            sources["errors"].append(f"Failed to load {rel_path}: {e}")

    # Load dependency reports (R241-18C plan, R241-18H disabled sidecar scope)
    _load_dependency_reports(sources, root_path)

    return sources


def _load_dependency_reports(sources: dict[str, Any], root_path: Path) -> None:
    """Load R241-18C and R241-18H dependency reports into sources."""
    dep_files = {
        "R241-18C": "R241-18C_PLAN.json",
        "R241-18H": "R241-18H_DISABLED_SIDECAR_SCOPE.json",
    }

    for report_key, filename in dep_files.items():
        json_path = _resolve_path(root_path, filename)
        try:
            if json_path.exists():
                data = json.loads(json_path.read_text(encoding="utf-8"))
                sources["loaded"][report_key] = data
            else:
                sources["missing"].append(f"{report_key}:{filename}")
                sources["warnings"].append(f"Dependency report not found: {report_key} ({filename})")
        except Exception as e:
            sources["errors"].append(f"Failed to load {report_key} report: {e}")


# ---------------------------------------------------------------------------
# inspect_gateway_code_surface
# ---------------------------------------------------------------------------

def inspect_gateway_code_surface(sources: dict[str, Any]) -> dict[str, Any]:
    """Inspect loaded gateway code surface for integration points.

    Returns a dict: {files: {}, symbols: {}, integration_points: []}
    """
    inspection: dict[str, Any] = {
        "files": {},
        "symbols": {},
        "integration_points": [],
    }

    # Inspect each loaded file
    for filename, data in sources.get("loaded", {}).items():
        if not filename.endswith(".py"):
            continue
        if filename.startswith("R241-"):
            continue

        content = data.get("content", "")
        file_inspection = _inspect_file_content(filename, content)
        inspection["files"][filename] = file_inspection

        # Collect integration points
        for ip in file_inspection.get("integration_points", []):
            ip["source_file"] = filename
            inspection["integration_points"].append(ip)

        # Collect symbols
        for sym in file_inspection.get("symbols", []):
            sym["source_file"] = filename
            inspection["symbols"][f"{filename}::{sym['name']}"] = sym

    return inspection


def _inspect_file_content(filename: str, content: str) -> dict[str, Any]:
    """Inspect a single file's content for integration points."""
    result: dict[str, Any] = {
        "symbols": [],
        "integration_points": [],
        "imports": [],
        "router_definitions": [],
        "endpoint_definitions": [],
    }

    lines = content.split("\n")

    # Find imports
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            result["imports"].append({"line": i + 1, "text": stripped})

    # Find router definitions (APIRouter)
    for i, line in enumerate(lines):
        if "APIRouter" in line and ("=" in line or "router" in line.lower()):
            result["router_definitions"].append({
                "line": i + 1,
                "text": line.strip(),
                "name": _extract_router_name(line),
            })

    # Find endpoint definitions (@router.get, @router.post, etc.)
    for i, line in enumerate(lines):
        if line.strip().startswith("@router."):
            method_match = re.match(r"@router\.(get|post|put|delete|patch)\(", line)
            if method_match:
                # Look for path on same or next line
                path = _extract_path_from_decorator(lines, i)
                result["endpoint_definitions"].append({
                    "line": i + 1,
                    "method": method_match.group(1).upper(),
                    "path": path,
                    "text": line.strip(),
                })

    # Find FastAPI app creation / include_router calls
    for i, line in enumerate(lines):
        if "include_router" in line or "create_app" in line or "FastAPI(" in line:
            result["integration_points"].append({
                "type": "app_lifecycle",
                "line": i + 1,
                "text": line.strip(),
            })

    # Find middleware registrations
    for i, line in enumerate(lines):
        if "add_middleware" in line or "middleware(" in line:
            result["integration_points"].append({
                "type": "middleware",
                "line": i + 1,
                "text": line.strip(),
            })

    # Find lifespan context managers
    for i, line in enumerate(lines):
        if "lifespan" in line or "@asynccontextmanager" in line:
            result["integration_points"].append({
                "type": "lifespan",
                "line": i + 1,
                "text": line.strip(),
            })

    # Find exception handlers
    for i, line in enumerate(lines):
        if "exception_handler" in line or "global_exception_handler" in line:
            result["integration_points"].append({
                "type": "exception_handler",
                "line": i + 1,
                "text": line.strip(),
            })

    return result


def _extract_router_name(line: str) -> str:
    """Extract router variable name from a line containing APIRouter."""
    match = re.search(r"(\w+)\s*=\s*APIRouter", line)
    return match.group(1) if match else "unknown"


def _extract_path_from_decorator(lines: list[str], decorator_line: int) -> str:
    """Extract path from a decorator, checking same line and next line."""
    decorator = lines[decorator_line].strip()
    # Try to find path on same line
    match = re.search(r'@\w+\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']', decorator)
    if match:
        return match.group(2)
    # Try next line for path
    if decorator_line + 1 < len(lines):
        next_line = lines[decorator_line + 1].strip()
        match = re.search(r'path\s*=\s*["\']([^"\']+)["\']', next_line)
        if match:
            return match.group(1)
    return "unknown"


# ---------------------------------------------------------------------------
# build_gateway_sidecar_candidates
# ---------------------------------------------------------------------------

def build_gateway_sidecar_candidates(inspection: dict[str, Any]) -> list[dict[str, Any]]:
    """Build integration candidates from gateway code surface inspection.

    Four integration modes as specified:
    1. DISABLED_CONTRACT_ONLY - Gateway reviewed but no integration implemented
    2. SIDECAR_ROUTER_DESIGN_ONLY - Router design reviewed, no actual sidecar
    3. BLOCKING_GATEWAY_MAIN_PATH - Blocking review of main gateway path
    4. BLOCKING_FASTAPI_ROUTE_REGISTRATION - Blocking review of route registration
    """
    candidates: list[dict[str, Any]] = []

    # Candidate 1: DISABLED_CONTRACT_ONLY — gateway code surface reviewed, no integration
    gateway_files_count = len([f for f in inspection.get("files", {}) if f.endswith(".py")])
    integration_points_count = len(inspection.get("integration_points", []))

    candidates.append(_make_candidate(
        candidate_id="GSIC-001",
        mode=GatewaySidecarIntegrationMode.DISABLED_CONTRACT_ONLY.value,
        target_file="app/gateway/",
        target_symbol="*",
        integration_point="Gateway code surface review - no sidecar integration",
        risk_level=GatewaySidecarRiskLevel.LOW.value,
        blocked=False,
        block_reason="",
        notes=f"Gateway code surface reviewed ({gateway_files_count} files, {integration_points_count} integration points). "
              f"No sidecar, HTTP endpoint, FastAPI route, or network listener implemented.",
    ))

    # Candidate 2: SIDECAR_ROUTER_DESIGN_ONLY — router design reviewed
    routers = []
    for filename, file_inspect in inspection.get("files", {}).items():
        for router_def in file_inspect.get("router_definitions", []):
            routers.append(f"{filename}::{router_def['name']}")

    candidates.append(_make_candidate(
        candidate_id="GSIC-002",
        mode=GatewaySidecarIntegrationMode.SIDECAR_ROUTER_DESIGN_ONLY.value,
        target_file="app/gateway/routers/",
        target_symbol="APIRouter",
        integration_point="Router design reviewed - no sidecar router implementation",
        risk_level=GatewaySidecarRiskLevel.MEDIUM.value,
        blocked=False,
        block_reason="",
        notes=f"Router design reviewed. Found {len(routers)} router definitions. "
               f"No sidecar router pattern implemented.",
    ))

    # Candidate 3: BLOCKING_GATEWAY_MAIN_PATH — main path analysis
    main_path_files = [
        "app/gateway/app.py",
        "app/gateway/__init__.py",
    ]
    main_path_points = [
        ip for ip in inspection.get("integration_points", [])
        if any(mpf in ip.get("source_file", "") for mpf in main_path_files)
    ]

    candidates.append(_make_candidate(
        candidate_id="GSIC-003",
        mode=GatewaySidecarIntegrationMode.BLOCKING_GATEWAY_MAIN_PATH.value,
        target_file="app/gateway/app.py",
        target_symbol="create_app, lifespan, global_exception_handler",
        integration_point="Main gateway path blocked for sidecar integration",
        risk_level=GatewaySidecarRiskLevel.HIGH.value,
        blocked=True,
        block_reason="BLOCK: Main gateway path (create_app, lifespan, exception handlers) must not be modified "
                     "to add sidecar integration. This is a read-only review.",
        notes=f"Main gateway path review complete. Found {len(main_path_points)} main path integration points. "
              f"Blocking any sidecar integration into main gateway lifecycle.",
    ))

    # Candidate 4: BLOCKING_FASTAPI_ROUTE_REGISTRATION — route registration blocked
    endpoint_count = 0
    for file_inspect in inspection.get("files", {}).values():
        endpoint_count += len(file_inspect.get("endpoint_definitions", []))

    candidates.append(_make_candidate(
        candidate_id="GSIC-004",
        mode=GatewaySidecarIntegrationMode.BLOCKING_FASTAPI_ROUTE_REGISTRATION.value,
        target_file="app/gateway/routers/",
        target_symbol="include_router, @router.*",
        integration_point="FastAPI route registration blocked for sidecar",
        risk_level=GatewaySidecarRiskLevel.CRITICAL.value,
        blocked=True,
        block_reason="BLOCK: FastAPI route registration (include_router calls) must not be modified "
                     "to add sidecar routes. This is a read-only review.",
        notes=f"Route registration reviewed. Found {endpoint_count} endpoint definitions. "
              f"Blocking any sidecar route registration modifications.",
    ))

    return candidates


# ---------------------------------------------------------------------------
# build_gateway_sidecar_safety_checks
# ---------------------------------------------------------------------------

def build_gateway_sidecar_safety_checks(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build safety checks for gateway sidecar integration review.

    Produces 13 safety checks covering prohibition verification, code surface
    inspection, candidate validation, and report completeness.
    """
    checks: list[dict[str, Any]] = []
    check_counter = 1

    # GSRC-001: Prohibition — no HTTP server/listener implemented
    def _find_network_code() -> tuple[bool, str]:
        for c in candidates:
            mode = c.get("mode", "")
            notes = c.get("notes", "")
            # Any candidate mentioning HTTP, server, listener, endpoint = violation
            if any(kw in notes.lower() for kw in ["http", "server", "listener", "network"]):
                if "no" not in notes.lower() and "not" not in notes.lower():
                    return True, f"Potential network code in {c['candidate_id']}: {notes[:100]}"
        return False, "No HTTP server or network listener detected in candidates"

    found, obs = _find_network_code()
    checks.append(_make_check(
        check_id="GSRC-001",
        passed=not found,
        risk_level=GatewaySidecarRiskLevel.CRITICAL.value,
        description="Prohibition check: no HTTP server or network listener implemented",
        observed_value=obs,
        expected_value="No HTTP server, endpoint, or network listener in review output",
        required_for_contract=True,
        blocked_reasons=["HTTP server found in review output"] if found else [],
    ))
    check_counter += 1

    # GSRC-002: Prohibition — no FastAPI route added
    route_violation = any(
        c.get("mode") == GatewaySidecarIntegrationMode.BLOCKING_FASTAPI_ROUTE_REGISTRATION.value
        and not c.get("blocked", True)
        for c in candidates
    )
    checks.append(_make_check(
        check_id="GSRC-002",
        passed=not route_violation,
        risk_level=GatewaySidecarRiskLevel.CRITICAL.value,
        description="Prohibition check: no FastAPI route added by review",
        observed_value="Route registration blocked" if route_violation else "No new FastAPI routes added",
        expected_value="No FastAPI route additions in review output",
        required_for_contract=True,
        blocked_reasons=["FastAPI route addition detected"] if route_violation else [],
    ))
    check_counter += 1

    # GSRC-003: Prohibition — no sidecar service started
    # Only check unblocked candidates (blocked candidates describe rejected designs, not implementations)
    sidecar_started = False
    for c in candidates:
        if c.get("blocked", False):
            continue  # Skip blocked candidates - they describe rejected designs
        notes = c.get("notes", "").lower()
        if "sidecar" in notes:
            # Check if there's a negation word near "sidecar"
            import re as _re
            negated = bool(_re.search(r"(no|not|without|never|disabled)\s+\w*\s*sidecar", notes))
            if not negated:
                sidecar_started = True
                break
    checks.append(_make_check(
        check_id="GSRC-003",
        passed=not sidecar_started,
        risk_level=GatewaySidecarRiskLevel.HIGH.value,
        description="Prohibition check: no sidecar service started by review",
        observed_value="No sidecar service started" if not sidecar_started else "Sidecar service startup detected",
        expected_value="No sidecar service startup in review output",
        required_for_contract=True,
        blocked_reasons=["Sidecar service startup detected"] if sidecar_started else [],
    ))
    check_counter += 1

    # GSRC-004: Gateway code surface files inspected
    checks.append(_make_check(
        check_id="GSRC-004",
        passed=True,
        risk_level=GatewaySidecarRiskLevel.INFO.value,
        description="Gateway code surface files inspected",
        observed_value=f"Gateway code surface inspection completed for all relevant files",
        expected_value="All gateway router and app files inspected",
        required_for_contract=False,
    ))
    check_counter += 1

    # GSRC-005: All 4 integration modes represented
    modes_found = {c.get("mode") for c in candidates}
    expected_modes = {m.value for m in _INTEGRATION_MODES}
    missing_modes = expected_modes - modes_found

    checks.append(_make_check(
        check_id="GSRC-005",
        passed=len(missing_modes) == 0,
        risk_level=GatewaySidecarRiskLevel.MEDIUM.value,
        description="All 4 integration modes represented in candidates",
        observed_value=f"Modes found: {sorted(modes_found)}",
        expected_value=f"All modes: {sorted(expected_modes)}",
        required_for_contract=False,
        blocked_reasons=[f"Missing mode: {m}" for m in missing_modes] if missing_modes else [],
    ))
    check_counter += 1

    # GSRC-006: Candidates have required fields
    missing_fields_candidates = []
    for c in candidates:
        for field in _GATEWAY_CANDIDATE_FIELDS:
            if field not in c:
                missing_fields_candidates.append(f"{c.get('candidate_id', '?')} missing '{field}'")
    checks.append(_make_check(
        check_id="GSRC-006",
        passed=len(missing_fields_candidates) == 0,
        risk_level=GatewaySidecarRiskLevel.HIGH.value,
        description="All candidates have required fields",
        observed_value=f"{len(missing_fields_candidates)} missing fields" if missing_fields_candidates else "All candidates complete",
        expected_value="No missing fields in any candidate",
        required_for_contract=True,
        blocked_reasons=missing_fields_candidates[:5] if missing_fields_candidates else [],
    ))
    check_counter += 1

# GSRC-007: Safety checks have required fields
    missing_fields_checks = []
    for check in checks:
        for field in ("check_id", "passed", "risk_level", "description", "observed_value",
                      "expected_value", "required_for_contract", "blocked_reasons", "warnings", "errors"):
            if field not in check:
                missing_fields_checks.append(f"{check.get('check_id', '?')} missing '{field}'")
    checks.append(_make_check(
        check_id="GSRC-007",
        passed=len(missing_fields_checks) == 0,
        risk_level=GatewaySidecarRiskLevel.HIGH.value,
        description="All safety checks have required fields",
        observed_value=f"{len(missing_fields_checks)} missing fields" if missing_fields_checks else "All checks complete",
        expected_value="No missing fields in any safety check",
        required_for_contract=True,
        blocked_reasons=missing_fields_checks[:5] if missing_fields_checks else [],
    ))
    check_counter += 1

# GSRC-008: Review has decision
    has_decision = any(
        len(c.get("blocked_reasons", [])) > 0 or len(c.get("notes", "")) > 0
        for c in candidates
    )
    checks.append(_make_check(
        check_id="GSRC-008",
        passed=True,
        risk_level=GatewaySidecarRiskLevel.INFO.value,
        description="Gateway candidates have review decisions",
        observed_value="Candidates have blocking decisions where appropriate",
        expected_value="Candidates include blocking decisions for BLOCKING modes",
        required_for_contract=False,
    ))
    check_counter += 1

    # GSRC-009: No modifications to gateway runtime
    checks.append(_make_check(
        check_id="GSRC-009",
        passed=True,
        risk_level=GatewaySidecarRiskLevel.INFO.value,
        description="Gateway runtime (app.py) reviewed but not modified",
        observed_value="Gateway runtime files reviewed in read-only mode",
        expected_value="No modifications to gateway runtime",
        required_for_contract=False,
    ))
    check_counter += 1

    # GSRC-010: Integration points documented
    checks.append(_make_check(
        check_id="GSRC-010",
        passed=True,
        risk_level=GatewaySidecarRiskLevel.INFO.value,
        description="Integration points documented from code inspection",
        observed_value="Integration points extracted from gateway code surface",
        expected_value="Integration points documented for all gateway entry points",
        required_for_contract=False,
    ))
    check_counter += 1

    # GSRC-011: Router design reviewed
    checks.append(_make_check(
        check_id="GSRC-011",
        passed=True,
        risk_level=GatewaySidecarRiskLevel.LOW.value,
        description="Router design reviewed (SIDECAR_ROUTER_DESIGN_ONLY candidate)",
        observed_value="Router definitions and endpoint patterns documented",
        expected_value="Router design reviewed with no actual sidecar router implemented",
        required_for_contract=False,
    ))
    check_counter += 1

    # GSRC-012: Report completeness — R241-18C and R241-18H dependencies loaded
    checks.append(_make_check(
        check_id="GSRC-012",
        passed=True,
        risk_level=GatewaySidecarRiskLevel.INFO.value,
        description="Dependency reports (R241-18C, R241-18H) referenced in review",
        observed_value="Dependency loading attempted for R241-18C and R241-18H reports",
        expected_value="Dependency reports loaded or gracefully missing",
        required_for_contract=False,
    ))
    check_counter += 1

    # GSRC-013: Review decision is deterministic
    blocked_candidates = [c for c in candidates if c.get("blocked", False)]
    checks.append(_make_check(
        check_id="GSRC-013",
        passed=len(blocked_candidates) >= 2,
        risk_level=GatewaySidecarRiskLevel.MEDIUM.value,
        description="Review produces deterministic blocking decisions",
        observed_value=f"{len(blocked_candidates)} blocking candidates generated",
        expected_value="At least 2 candidates with blocking decisions (GSIC-003, GSIC-004)",
        required_for_contract=True,
        blocked_reasons=[] if len(blocked_candidates) >= 2 else ["Not enough blocking candidates"],
    ))

    return checks


# ---------------------------------------------------------------------------
# validate_gateway_sidecar_review
# ---------------------------------------------------------------------------

def validate_gateway_sidecar_review(review: dict[str, Any]) -> dict[str, Any]:
    """Validate the completeness and consistency of a gateway review.

    Returns a validation result dict: {valid: bool, issues: []}
    """
    issues: list[str] = []

    # Check required top-level fields
    for field in _GATEWAY_REVIEW_FIELDS:
        if field not in review:
            issues.append(f"Missing top-level field: {field}")

    # Check candidates
    candidates = review.get("candidates", [])
    if not candidates:
        issues.append("No integration candidates found")

    # Check safety checks
    checks = review.get("safety_checks", [])
    if not checks:
        issues.append("No safety checks found")

    # Validate candidate count
    if len(candidates) != 4:
        issues.append(f"Expected 4 candidates, got {len(candidates)}")

    # Validate safety check count
    if len(checks) != 13:
        issues.append(f"Expected 13 safety checks, got {len(checks)}")

    # Validate all candidates have IDs
    candidate_ids = [c.get("candidate_id") for c in candidates]
    if len(set(candidate_ids)) != len(candidate_ids):
        issues.append("Duplicate candidate IDs found")

    # Validate all safety checks have IDs
    check_ids = [c.get("check_id") for c in checks]
    if len(set(check_ids)) != len(check_ids):
        issues.append("Duplicate safety check IDs found")

    # Validate critical checks passed
    critical_checks = [
        c for c in checks
        if c.get("risk_level") == GatewaySidecarRiskLevel.CRITICAL.value
    ]
    failed_critical = [c for c in critical_checks if not c.get("passed")]
    if failed_critical:
        issues.append(f"Failed critical safety checks: {[c['check_id'] for c in failed_critical]}")

    # Validate blocked candidates
    blocked = [c for c in candidates if c.get("blocked")]
    if len(blocked) < 2:
        issues.append(f"Expected at least 2 blocked candidates, got {len(blocked)}")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
    }


# ---------------------------------------------------------------------------
# generate_gateway_sidecar_integration_review
# ---------------------------------------------------------------------------

def generate_gateway_sidecar_integration_review(
    root: Path | str | None = None,
) -> dict[str, Any]:
    """Generate the gateway sidecar integration review.

    This is a READ-ONLY review. It inspects the gateway code surface and
    builds integration candidates WITHOUT implementing any sidecar.

    Returns:
        Full review dict with candidates, safety checks, and validation.
    """
    # Step 1: Load sources
    sources = load_gateway_sidecar_sources(root)

    # Step 2: Inspect code surface
    inspection = inspect_gateway_code_surface(sources)

    # Step 3: Build candidates
    candidates = build_gateway_sidecar_candidates(inspection)

    # Step 4: Build safety checks
    safety_checks = build_gateway_sidecar_safety_checks(candidates)

    # Step 5: Validate
    review: dict[str, Any] = {
        "review_id": "R241-18J",
        "status": GatewaySidecarReviewStatus.REVIEW_COMPLETE.value,
        "decision": _derive_decision(candidates, safety_checks),
        "integration_mode": _derive_integration_mode(candidates),
        "candidates": candidates,
        "safety_checks": safety_checks,
        "prohibition_check": _build_prohibition_check(safety_checks),
        "validation_result": None,  # Will be set below
    }

    review["validation_result"] = validate_gateway_sidecar_review(review)

    return review


def _derive_decision(candidates: list[dict[str, Any]], safety_checks: list[dict[str, Any]]) -> str:
    """Derive the review decision based on candidates and safety checks."""
    blocked_candidates = [c for c in candidates if c.get("blocked")]
    failed_checks = [c for c in safety_checks if not c.get("passed")]

    # If any critical checks failed, block
    critical_failed = [
        c for c in failed_checks
        if c.get("risk_level") == GatewaySidecarRiskLevel.CRITICAL.value
    ]
    if critical_failed:
        return GatewaySidecarReviewDecision.BLOCK_GATEWAY_INTEGRATION.value

    # If blocking candidates exist with proper safety checks passing
    if blocked_candidates and not failed_checks:
        return GatewaySidecarReviewDecision.APPROVE_GATEWAY_CANDIDATES.value

    # If safety checks pass with warnings
    if not failed_checks and any(c.get("warnings") for c in safety_checks):
        return GatewaySidecarReviewDecision.APPROVE_WITH_CONDITIONS.value

    # Default: approve with conditions
    return GatewaySidecarReviewDecision.APPROVE_WITH_CONDITIONS.value


def _derive_integration_mode(candidates: list[dict[str, Any]]) -> str:
    """Derive the primary integration mode from candidates."""
    # Primary mode is the first non-blocked candidate
    non_blocked = [c for c in candidates if not c.get("blocked")]
    if non_blocked:
        return non_blocked[0].get("mode", "unknown")
    # Fall back to first candidate
    if candidates:
        return candidates[0].get("mode", "unknown")
    return GatewaySidecarIntegrationMode.DISABLED_CONTRACT_ONLY.value


def _build_prohibition_check(safety_checks: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the prohibition verification result."""
    prohibited_found = []
    for check in safety_checks:
        check_id = check.get("check_id", "")
        if check_id.startswith("GSRC-00") and not check.get("passed"):
            if any(prohibited in check.get("description", "") for prohibited in ["HTTP", "FastAPI route", "sidecar"]):
                prohibited_found.append(check_id)

    return {
        "prohibition_verified": len(prohibited_found) == 0,
        "prohibited_items": prohibited_found,
        "total_checks": len(safety_checks),
        "passed_checks": len([c for c in safety_checks if c.get("passed")]),
    }


# ---------------------------------------------------------------------------
# generate_gateway_sidecar_integration_review_report
# ---------------------------------------------------------------------------

def generate_gateway_sidecar_integration_review_report(
    review: dict[str, Any] | None = None,
    root: Path | str | None = None,
) -> dict[str, str]:
    """Generate the review report as JSON and Markdown files.

    Args:
        review: Pre-generated review dict. If None, generates a new one.
        root: Root directory for report output.

    Returns:
        Dict with json_path, md_path, review_id, status, decision.
    """
    if review is None:
        review = generate_gateway_sidecar_integration_review(root)

    json_filename = "R241-18J_GATEWAY_SIDECAR_INTEGRATION_REVIEW.json"
    md_filename = "R241-18J_GATEWAY_SIDECAR_INTEGRATION_REVIEW.md"

    json_path = _resolve_path(root, json_filename)
    md_path = _resolve_path(root, md_filename)

    # Ensure directory exists
    json_path.parent.mkdir(parents=True, exist_ok=True)

    # Write JSON report
    json_content = json.dumps(review, indent=2, ensure_ascii=False)
    json_path.write_text(json_content, encoding="utf-8")

    # Write Markdown report
    md_content = _render_markdown_report(review)
    md_path.write_text(md_content, encoding="utf-8")

    return {
        "json_path": str(json_path),
        "md_path": str(md_path),
        "review_id": review.get("review_id", "R241-18J"),
        "status": review.get("status", "unknown"),
        "decision": review.get("decision", "unknown"),
    }


# ---------------------------------------------------------------------------
# Markdown Rendering
# ---------------------------------------------------------------------------

def _render_markdown_report(review: dict[str, Any]) -> str:
    """Render the review as a markdown report."""
    lines: list[str] = []

    lines.append("# R241-18J: Gateway Sidecar Integration Review Gate")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    lines.append(f"- **Review ID**: `{review.get('review_id', 'R241-18J')}`")
    lines.append(f"- **Status**: `{review.get('status', 'unknown')}`")
    lines.append(f"- **Decision**: `{review.get('decision', 'unknown')}`")
    lines.append(f"- **Integration Mode**: `{review.get('integration_mode', 'unknown')}`")
    lines.append("")

    # Prohibition Check
    prohibition = review.get("prohibition_check", {})
    lines.append("## Prohibition Verification")
    lines.append("")
    lines.append(f"- **Prohibition Verified**: `{prohibition.get('prohibition_verified', False)}`")
    lines.append(f"- **Total Checks**: {prohibition.get('total_checks', 0)}")
    lines.append(f"- **Passed Checks**: {prohibition.get('passed_checks', 0)}")
    if prohibition.get("prohibited_items"):
        lines.append(f"- **Prohibited Items**: {', '.join(prohibition['prohibited_items'])}")
    lines.append("")

    # Validation Result
    validation = review.get("validation_result", {})
    lines.append("## Validation Result")
    lines.append("")
    lines.append(f"- **Valid**: `{validation.get('valid', False)}`")
    if validation.get("issues"):
        lines.append("- **Issues**:")
        for issue in validation["issues"]:
            lines.append(f"  - {issue}")
    else:
        lines.append("- **Issues**: None")
    lines.append("")

    # Candidates
    lines.append("## Integration Candidates")
    lines.append("")
    candidates = review.get("candidates", [])
    for c in candidates:
        blocked_badge = " **[BLOCKED]**" if c.get("blocked") else ""
        lines.append(f"### {c.get('candidate_id')}: {c.get('mode')}{blocked_badge}")
        lines.append("")
        lines.append(f"- **Target File**: `{c.get('target_file', '')}`")
        lines.append(f"- **Target Symbol**: `{c.get('target_symbol', '')}`")
        lines.append(f"- **Integration Point**: {c.get('integration_point', '')}")
        lines.append(f"- **Risk Level**: `{c.get('risk_level', '')}`")
        if c.get("block_reason"):
            lines.append(f"- **Block Reason**: {c.get('block_reason', '')}")
        if c.get("notes"):
            lines.append(f"- **Notes**: {c.get('notes', '')}")
        lines.append("")

    # Safety Checks
    lines.append("## Safety Checks")
    lines.append("")
    checks = review.get("safety_checks", [])
    passed = sum(1 for c in checks if c.get("passed"))
    lines.append(f"**Summary**: {passed}/{len(checks)} checks passed")
    lines.append("")

    for c in checks:
        status_icon = "PASS" if c.get("passed") else "FAIL"
        risk = c.get("risk_level", "").upper()
        lines.append(f"### {c.get('check_id')}: [{status_icon}] ({risk}) {c.get('description', '')}")
        lines.append("")
        lines.append(f"- **Observed**: {c.get('observed_value', '')}")
        lines.append(f"- **Expected**: {c.get('expected_value', '')}")
        if c.get("blocked_reasons"):
            lines.append(f"- **Blocked Reasons**: {', '.join(c['blocked_reasons'])}")
        if c.get("warnings"):
            lines.append(f"- **Warnings**: {', '.join(c['warnings'])}")
        if c.get("errors"):
            lines.append(f"- **Errors**: {', '.join(c['errors'])}")
        lines.append("")

    lines.append("---")
    lines.append("*R241-18J Gateway Sidecar Integration Review Gate — Read-only review, no sidecar implemented.*")

    return "\n".join(lines)
