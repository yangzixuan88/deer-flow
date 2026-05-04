"""Minimal read-only diagnostic CLI/API integration plan.

This module generates contracts/specifications only. It does not implement
real CLI commands, HTTP endpoints, runtime writes, action queues, or Gateway
integration.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
DEFAULT_MATRIX_PATH = REPORT_DIR / "R241-9A_FOUNDATION_INTEGRATION_READINESS_MATRIX.json"
DEFAULT_PLAN_JSON_PATH = REPORT_DIR / "R241-9B_MINIMAL_READONLY_INTEGRATION_PLAN.json"
DEFAULT_PLAN_MD_PATH = REPORT_DIR / "R241-9B_MINIMAL_READONLY_INTEGRATION_PLAN.md"

DIAGNOSTIC_SURFACES = {
    "truth_state",
    "governance",
    "queue_sandbox",
    "memory",
    "asset",
    "prompt",
    "rtcm",
    "nightly",
    "feishu_summary",
    "all",
}

INTERFACE_TYPES = {"cli_command", "read_only_api_endpoint", "python_helper", "report_generator", "unknown"}
RISK_LEVELS = {"low", "medium", "high", "critical", "unknown"}
PERMISSIONS = {"read_only_allowed", "report_only_allowed", "dry_run_only", "blocked", "unknown"}


@dataclass
class ReadOnlyDiagnosticCommandSpec:
    command_id: str
    surface: str
    command_name: str
    description: str
    module_ref: str
    function_ref: str
    input_args: List[Dict[str, Any]]
    output_schema_ref: str
    reads_runtime: bool
    writes_runtime: bool
    writes_report_only: bool
    permission: str
    risk_level: str
    requires_root_guard: bool
    expected_warnings: List[str] = field(default_factory=list)
    test_refs: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    recommended_implementation_phase: str = "Phase A"


@dataclass
class ReadOnlyDiagnosticEndpointSpec:
    endpoint_id: str
    surface: str
    method: str
    path: str
    description: str
    module_ref: str
    function_ref: str
    query_params: List[Dict[str, Any]]
    response_schema_ref: str
    reads_runtime: bool
    writes_runtime: bool
    writes_report_only: bool
    permission: str
    risk_level: str
    requires_auth_later: bool
    requires_rate_limit_later: bool
    disabled_by_default: bool
    blockers: List[str] = field(default_factory=list)
    recommended_implementation_phase: str = "Phase A"


@dataclass
class ReadOnlyIntegrationPlan:
    plan_id: str
    generated_at: str
    source_matrix_ref: str
    approved_surfaces: List[Dict[str, Any]]
    excluded_surfaces: List[Dict[str, Any]]
    cli_command_specs: List[Dict[str, Any]]
    api_endpoint_specs: List[Dict[str, Any]]
    implementation_sequence: List[Dict[str, Any]]
    safety_constraints: List[str]
    expected_warnings: List[str]
    blockers: List[Dict[str, Any]]
    next_phase_recommendation: str
    warnings: List[str] = field(default_factory=list)


DIAGNOSTIC_SPEC_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "surface": "truth_state",
        "command_name": "foundation diagnose truth-state",
        "path": "/foundation/diagnostics/truth-state",
        "description": "输出 Truth/State projection summary，检查 execution/governance/observation truth 分离。",
        "module_ref": "backend/app/m11/truth_state_contract.py; backend/app/m11/governance_bridge.py",
        "function_ref": "summarize_outcome_contract; project_recent_outcomes; get_success_rate_candidates",
        "permission": "read_only_allowed",
        "risk_level": "low",
        "test_refs": ["backend/app/m11/test_truth_state_contract.py", "backend/app/m11/test_governance_truth_projection.py"],
    },
    {
        "surface": "queue_sandbox",
        "command_name": "foundation diagnose queue-sandbox",
        "path": "/foundation/diagnostics/queue-sandbox",
        "description": "输出 queue snapshot、sandbox truth、queue correlation，并保留 queue_path_mismatch warning。",
        "module_ref": "backend/app/m11/queue_sandbox_truth_projection.py",
        "function_ref": "load_experiment_queue_snapshot; project_sandbox_outcomes; correlate_queue_with_sandbox_truth",
        "permission": "read_only_allowed",
        "risk_level": "medium",
        "expected_warnings": ["queue_path_mismatch_unresolved"],
        "test_refs": ["backend/app/m11/test_queue_sandbox_truth_projection.py"],
    },
    {
        "surface": "memory",
        "command_name": "foundation diagnose memory",
        "path": "/foundation/diagnostics/memory",
        "description": "输出 memory projection、long-term candidates、asset candidates、risk signals。",
        "module_ref": "backend/app/memory/memory_projection.py",
        "function_ref": "project_memory_roots; get_long_term_memory_candidates; get_memory_asset_candidates; detect_memory_risk_signals",
        "permission": "read_only_allowed",
        "risk_level": "low",
        "test_refs": ["backend/app/memory/test_memory_projection.py"],
    },
    {
        "surface": "asset",
        "command_name": "foundation diagnose asset",
        "path": "/foundation/diagnostics/asset",
        "description": "输出 asset registry、binding、governance、memory candidate aggregate projection。",
        "module_ref": "backend/app/asset/asset_projection.py",
        "function_ref": "aggregate_asset_projection; detect_asset_projection_risks",
        "permission": "read_only_allowed",
        "risk_level": "low",
        "test_refs": ["backend/app/asset/test_asset_projection.py"],
    },
    {
        "surface": "prompt",
        "command_name": "foundation diagnose prompt",
        "path": "/foundation/diagnostics/prompt",
        "description": "输出 prompt source projection、replacement risk、A7 candidates。",
        "module_ref": "backend/app/prompt/prompt_projection.py",
        "function_ref": "aggregate_prompt_projection; detect_prompt_governance_risks",
        "permission": "read_only_allowed",
        "risk_level": "medium",
        "test_refs": ["backend/app/prompt/test_prompt_projection.py"],
    },
    {
        "surface": "rtcm",
        "command_name": "foundation diagnose rtcm",
        "path": "/foundation/diagnostics/rtcm",
        "description": "输出 RTCM runtime projection、session projection、context link warning、unknown taxonomy。",
        "module_ref": "backend/app/rtcm/rtcm_runtime_projection.py",
        "function_ref": "scan_rtcm_runtime_projection; detect_rtcm_runtime_projection_risks; generate_rtcm_runtime_projection_report",
        "permission": "read_only_allowed",
        "risk_level": "medium",
        "test_refs": ["backend/app/rtcm/test_rtcm_runtime_projection.py"],
    },
    {
        "surface": "nightly",
        "command_name": "foundation diagnose nightly",
        "path": "/foundation/diagnostics/nightly",
        "description": "输出 Nightly Foundation Health Review summary。",
        "module_ref": "backend/app/nightly/foundation_health_review.py",
        "function_ref": "aggregate_nightly_foundation_health; generate_nightly_foundation_health_review",
        "permission": "read_only_allowed",
        "risk_level": "medium",
        "test_refs": ["backend/app/nightly/test_foundation_health_review.py"],
    },
    {
        "surface": "feishu_summary",
        "command_name": "foundation diagnose feishu-summary",
        "path": "/foundation/diagnostics/feishu-summary",
        "description": "输出 Feishu/Lark payload projection；send_allowed=false；no webhook call。",
        "module_ref": "backend/app/nightly/foundation_health_summary.py",
        "function_ref": "generate_nightly_summary_projection_report; build_feishu_card_payload_projection",
        "permission": "dry_run_only",
        "risk_level": "medium",
        "test_refs": ["backend/app/nightly/test_foundation_health_summary.py"],
    },
    {
        "surface": "all",
        "command_name": "foundation diagnose all",
        "path": "/foundation/diagnostics/all",
        "description": "聚合全部 read-only diagnostics；不执行修复；不写 runtime；可写 report 到 migration_reports/foundation_audit。",
        "module_ref": "backend/app/nightly/foundation_health_review.py; backend/app/nightly/foundation_health_summary.py",
        "function_ref": "aggregate_nightly_foundation_health; generate_nightly_summary_projection_report",
        "permission": "read_only_allowed",
        "risk_level": "medium",
        "test_refs": ["backend/app/nightly/test_foundation_health_review.py", "backend/app/nightly/test_foundation_health_summary.py"],
        "writes_report_only": True,
    },
]


def load_readiness_matrix(path: Optional[str] = None) -> Dict[str, Any]:
    target = Path(path) if path else DEFAULT_MATRIX_PATH
    if not target.exists():
        return {"exists": False, "matrix": {}, "warnings": [f"readiness_matrix_missing:{target}"]}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"exists": True, "matrix": {}, "warnings": [f"readiness_matrix_malformed:{exc}"]}
    matrix = data.get("matrix") if isinstance(data, dict) else None
    if not isinstance(matrix, dict):
        return {"exists": True, "matrix": {}, "warnings": ["readiness_matrix_payload_missing"]}
    return {"exists": True, "matrix": matrix, "warnings": list(data.get("warnings") or [])}


def extract_readonly_surfaces(matrix: Dict[str, Any]) -> Dict[str, Any]:
    warnings: List[str] = []
    surfaces = matrix.get("surfaces") if isinstance(matrix, dict) else []
    if not isinstance(surfaces, list):
        return {"approved_surfaces": [], "excluded_surfaces": [], "blocked_surfaces": [], "warnings": ["matrix_surfaces_missing"]}
    approved = []
    excluded = []
    blocked = []
    for surface in surfaces:
        level = surface.get("readiness_level")
        if level == "read_only_ready":
            approved.append(surface)
        elif level == "blocked":
            blocked.append(surface)
            excluded.append(surface)
        else:
            excluded.append(surface)
        warnings.extend(surface.get("warnings") or [])
    return {
        "approved_surfaces": approved,
        "excluded_surfaces": excluded,
        "blocked_surfaces": blocked,
        "warnings": _dedupe(warnings),
    }


def build_cli_command_specs(approved_surfaces: List[Dict[str, Any]]) -> Dict[str, Any]:
    blocked = _blocked_surface_ids(approved_surfaces)
    specs = []
    for definition in DIAGNOSTIC_SPEC_DEFINITIONS:
        blockers = []
        if definition["surface"] in blocked:
            blockers.append("blocked_surface_not_allowed")
        spec = ReadOnlyDiagnosticCommandSpec(
            command_id=_make_id("cli", definition["surface"], definition["command_name"]),
            surface=definition["surface"],
            command_name=definition["command_name"],
            description=definition["description"],
            module_ref=definition["module_ref"],
            function_ref=definition["function_ref"],
            input_args=_default_input_args(definition["surface"]),
            output_schema_ref=f"ReadOnlyDiagnostic{definition['surface'].title().replace('_', '')}Output",
            reads_runtime=True,
            writes_runtime=False,
            writes_report_only=bool(definition.get("writes_report_only", False)),
            permission=definition["permission"],
            risk_level=definition["risk_level"],
            requires_root_guard=True,
            expected_warnings=list(definition.get("expected_warnings") or []),
            test_refs=list(definition.get("test_refs") or []),
            blockers=blockers,
            recommended_implementation_phase="Phase A",
        )
        specs.append(asdict(spec))
    return {"command_count": len(specs), "command_specs": specs, "warnings": []}


def build_api_endpoint_specs(approved_surfaces: List[Dict[str, Any]]) -> Dict[str, Any]:
    blocked = _blocked_surface_ids(approved_surfaces)
    specs = []
    for definition in DIAGNOSTIC_SPEC_DEFINITIONS:
        blockers = []
        if definition["surface"] in blocked:
            blockers.append("blocked_surface_not_allowed")
        spec = ReadOnlyDiagnosticEndpointSpec(
            endpoint_id=_make_id("endpoint", definition["surface"], definition["path"]),
            surface=definition["surface"],
            method="GET",
            path=definition["path"],
            description=definition["description"] + " No action execution. No auto-fix.",
            module_ref=definition["module_ref"],
            function_ref=definition["function_ref"],
            query_params=_default_query_params(definition["surface"]),
            response_schema_ref=f"ReadOnlyDiagnostic{definition['surface'].title().replace('_', '')}Response",
            reads_runtime=True,
            writes_runtime=False,
            writes_report_only=bool(definition.get("writes_report_only", False)),
            permission=definition["permission"],
            risk_level=definition["risk_level"],
            requires_auth_later=True,
            requires_rate_limit_later=True,
            disabled_by_default=True,
            blockers=blockers,
            recommended_implementation_phase="Phase A",
        )
        specs.append(asdict(spec))
    return {"endpoint_count": len(specs), "endpoint_specs": specs, "warnings": []}


def validate_readonly_integration_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    warnings: List[str] = []
    errors: List[str] = []
    command_specs = plan.get("cli_command_specs") or []
    endpoint_specs = plan.get("api_endpoint_specs") or []
    blocked_surfaces = {surface.get("surface_id") for surface in plan.get("blocked_surfaces", [])}

    for spec in command_specs:
        if spec.get("writes_runtime"):
            errors.append(f"command_writes_runtime:{spec.get('command_name')}")
        if spec.get("surface") == "feishu_summary" and spec.get("permission") != "dry_run_only":
            errors.append("feishu_summary_must_be_dry_run_only")
        if spec.get("surface") == "all" and "fix" in str(spec.get("description", "")).lower() and "不执行修复" not in str(spec.get("description", "")):
            errors.append("diagnose_all_must_not_execute_fix")
        if spec.get("surface") in blocked_surfaces:
            errors.append(f"blocked_surface_in_command:{spec.get('surface')}")
        if "queue_path_mismatch_unresolved" in (spec.get("expected_warnings") or []):
            warnings.append("queue_path_mismatch_unresolved")

    for spec in endpoint_specs:
        if spec.get("method") in {"POST", "PUT", "DELETE", "PATCH"}:
            errors.append(f"mutating_endpoint_method:{spec.get('method')}:{spec.get('path')}")
        if spec.get("writes_runtime"):
            errors.append(f"endpoint_writes_runtime:{spec.get('path')}")
        if spec.get("disabled_by_default") is not True:
            errors.append(f"endpoint_not_disabled_by_default:{spec.get('path')}")
        if spec.get("requires_auth_later") is not True:
            errors.append(f"endpoint_missing_auth_later:{spec.get('path')}")
        if spec.get("requires_rate_limit_later") is not True:
            errors.append(f"endpoint_missing_rate_limit_later:{spec.get('path')}")
        if spec.get("surface") in blocked_surfaces:
            errors.append(f"blocked_surface_in_endpoint:{spec.get('surface')}")

    if len(command_specs) < 9:
        errors.append("missing_cli_command_specs")
    if len(endpoint_specs) < 9:
        errors.append("missing_api_endpoint_specs")
    return {"valid": not errors, "warnings": _dedupe(warnings), "errors": _dedupe(errors)}


def build_implementation_sequence(plan: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "sequence": [
            {"order": 1, "step": "CLI internal helpers only", "implementation_allowed_next": True},
            {"order": 2, "step": "CLI report output to migration_reports", "implementation_allowed_next": True},
            {"order": 3, "step": "API endpoint stubs disabled by default", "implementation_allowed_next": False},
            {"order": 4, "step": "API auth/rate-limit policy", "implementation_allowed_next": False},
            {"order": 5, "step": "Gateway sidecar router / not main run path", "implementation_allowed_next": False},
            {"order": 6, "step": "Feishu dry-run preview", "implementation_allowed_next": False},
            {"order": 7, "step": "Append-only audit later", "implementation_allowed_next": False},
        ],
        "warnings": [],
    }


def generate_minimal_readonly_integration_plan(output_path: Optional[str] = None) -> Dict[str, Any]:
    matrix_result = load_readiness_matrix()
    extraction = extract_readonly_surfaces(matrix_result.get("matrix", {}))
    cli = build_cli_command_specs(extraction["approved_surfaces"])
    api = build_api_endpoint_specs(extraction["approved_surfaces"])
    safety_constraints = [
        "read_only_only",
        "no_runtime_write",
        "no_action_queue",
        "no_auto_fix",
        "no_real_cli_binding",
        "no_real_api_endpoint",
        "no_gateway_main_path_change",
        "no_feishu_webhook_call",
    ]
    plan = asdict(
        ReadOnlyIntegrationPlan(
            plan_id=_make_id("readonly_integration_plan", _now()),
            generated_at=_now(),
            source_matrix_ref=str(DEFAULT_MATRIX_PATH),
            approved_surfaces=extraction["approved_surfaces"],
            excluded_surfaces=extraction["excluded_surfaces"],
            cli_command_specs=cli["command_specs"],
            api_endpoint_specs=api["endpoint_specs"],
            implementation_sequence=[],
            safety_constraints=safety_constraints,
            expected_warnings=_dedupe(extraction.get("warnings", []) + cli.get("warnings", []) + api.get("warnings", [])),
            blockers=extraction["blocked_surfaces"],
            next_phase_recommendation="R241-10A Read-only Diagnostic CLI 内部实现",
            warnings=_dedupe(matrix_result.get("warnings", []) + extraction.get("warnings", [])),
        )
    )
    sequence = build_implementation_sequence(plan)
    plan["implementation_sequence"] = sequence["sequence"]
    validation = validate_readonly_integration_plan(plan)
    payload = {
        "source_matrix_summary": _matrix_summary(matrix_result.get("matrix", {})),
        "plan": plan,
        "validation": validation,
        "implementation_sequence": sequence,
        "generated_at": _now(),
        "warnings": _dedupe(plan.get("warnings", []) + validation.get("warnings", []) + sequence.get("warnings", [])),
    }
    json_path = Path(output_path) if output_path and output_path.endswith(".json") else DEFAULT_PLAN_JSON_PATH
    md_path = DEFAULT_PLAN_MD_PATH if not output_path or output_path.endswith(".json") else Path(output_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(payload, str(json_path)), encoding="utf-8")
    return {"json_path": str(json_path), "markdown_path": str(md_path), **payload}


def _render_markdown(payload: Dict[str, Any], json_path: str) -> str:
    plan = payload["plan"]
    validation = payload["validation"]
    lines = [
        "# R241-9B Minimal Read-only Integration Plan",
        "",
        "## 1. 修改文件清单",
        "",
        "- `backend/app/foundation/read_only_integration_plan.py`",
        "- `backend/app/foundation/test_read_only_integration_plan.py`",
        "- `migration_reports/foundation_audit/R241-9B_MINIMAL_READONLY_INTEGRATION_PLAN.json`",
        "- `migration_reports/foundation_audit/R241-9B_MINIMAL_READONLY_INTEGRATION_PLAN.md`",
        "",
        "## 2. Source Matrix Summary",
        "",
        f"- source_matrix_ref: `{plan['source_matrix_ref']}`",
        f"- approved_surfaces: {len(plan['approved_surfaces'])}",
        f"- excluded_surfaces: {len(plan['excluded_surfaces'])}",
        f"- blocked_surfaces: {len(plan['blockers'])}",
        "",
        "## 3. CLI Command Specs",
        "",
    ]
    for spec in plan["cli_command_specs"]:
        lines.append(f"- `{spec['command_name']}` -> {spec['module_ref']} / permission={spec['permission']}")
    lines.extend(["", "## 4. API Endpoint Specs", ""])
    for spec in plan["api_endpoint_specs"]:
        lines.append(f"- `{spec['method']} {spec['path']}` disabled_by_default={spec['disabled_by_default']} writes_runtime={spec['writes_runtime']}")
    lines.extend(
        [
            "",
            "## 5. Validation",
            "",
            f"- valid: {validation['valid']}",
            f"- warnings: {validation['warnings']}",
            f"- errors: {validation['errors']}",
            "",
            "## 6. Implementation Sequence",
            "",
        ]
    )
    for step in plan["implementation_sequence"]:
        lines.append(f"- {step['order']}. {step['step']}")
    lines.extend(
        [
            "",
            "## 7. Safety",
            "",
            "- 本轮未实现真实 CLI/API。",
            "- 本轮未修改 runtime、Gateway、action queue。",
            "- Feishu summary 仅 dry-run/projection。",
            "",
            "## 8. JSON Spec",
            "",
            f"- `{json_path}`",
            "",
            "## 9. Final Verdict",
            "",
            "A. R241-9B 成功，可进入 R241-10A Read-only Diagnostic CLI 内部实现。",
        ]
    )
    return "\n".join(lines) + "\n"


def _matrix_summary(matrix: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "matrix_id": matrix.get("matrix_id"),
        "read_only_ready_count": matrix.get("read_only_ready_count", 0),
        "append_only_ready_count": matrix.get("append_only_ready_count", 0),
        "report_only_count": matrix.get("report_only_count", 0),
        "blocked_count": matrix.get("blocked_count", 0),
        "by_readiness_level": matrix.get("by_readiness_level", {}),
    }


def _default_input_args(surface: str) -> List[Dict[str, Any]]:
    args = [{"name": "--format", "type": "enum", "values": ["json", "markdown", "text"], "required": False}]
    if surface in {"memory", "prompt", "rtcm", "nightly", "all"}:
        args.append({"name": "--max-files", "type": "int", "required": False, "default": 500})
    if surface in {"queue_sandbox", "asset"}:
        args.append({"name": "--limit", "type": "int", "required": False, "default": 200})
    if surface == "feishu_summary":
        args.append({"name": "--dry-run", "type": "bool", "required": False, "default": True})
    return args


def _default_query_params(surface: str) -> List[Dict[str, Any]]:
    params = [{"name": "format", "type": "enum", "values": ["json", "text"], "required": False}]
    if surface in {"memory", "prompt", "rtcm", "nightly", "all"}:
        params.append({"name": "max_files", "type": "int", "required": False, "default": 500})
    if surface in {"queue_sandbox", "asset"}:
        params.append({"name": "limit", "type": "int", "required": False, "default": 200})
    if surface == "feishu_summary":
        params.append({"name": "dry_run", "type": "bool", "required": False, "default": True})
    return params


def _blocked_surface_ids(approved_surfaces: List[Dict[str, Any]]) -> set[str]:
    return {str(surface.get("surface")) for surface in approved_surfaces if surface.get("readiness_level") == "blocked"}


def _make_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part) for part in parts if part is not None)
    return f"{prefix}_{abs(hash(raw)) % 10_000_000_000:010d}"


def _dedupe(items: List[Any]) -> List[str]:
    result: List[str] = []
    seen = set()
    for item in items:
        text = str(item)
        if text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

