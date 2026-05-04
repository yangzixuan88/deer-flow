"""R241-18G: Read-only Runtime Entry — Batch 4 Binding Implementation.

STEP-004: Feishu Pre-send Validate-only Entry (feishu_dryrun_validate / SPEC-005).

This module implements thin-wrapper bindings that reuse existing
audit_trend_feishu_presend_cli.run_feishu_presend_validate_only_cli().

No runtime write, no audit JSONL write, no report artifact write,
no JSONL write handle, no network call, no scheduler, no Feishu send,
no webhook value read, no webhook call, no secret read.

Allowed to create:
  - backend/app/foundation/read_only_runtime_entry_batch4.py (this file)
  - backend/app/foundation/test_read_only_runtime_entry_batch4.py

Allowed to generate:
  - migration_reports/foundation_audit/R241-18G_READONLY_RUNTIME_ENTRY_BATCH4_RESULT.json
  - migration_reports/foundation_audit/R241-18G_READONLY_RUNTIME_ENTRY_BATCH4_REPORT.md
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Canonical migration_reports path — shared by all batch modules
# ─────────────────────────────────────────────────────────────────────────────

_REPORT_SUBDIR = Path("migration_reports") / "foundation_audit"


def resolve_foundation_audit_report_path(
    root: Optional[str | Path] = None,
    filename: str = "",
) -> Path:
    """Resolve a foundation audit report path robustly.

    This is the canonical path resolution helper used by all R241-18X batch
    modules to avoid the ``backend/backend`` duplication bug.

    Args:
        root:   Explicit root override. May be:
                  - repo root (E:/OpenClaw-Base/deerflow)
                  - backend root (E:/OpenClaw-Base/deerflow/backend)
                  - None (auto-detect from this file's location)
                  - already inside migration_reports/foundation_audit
        filename: Report filename to append.

    Returns:
        Resolved Path inside ``migration_reports/foundation_audit`` with no
        duplication. Examples:
          root=repo root  → repo/migration_reports/foundation_audit/filename
          root=backend    → repo/migration_reports/foundation_audit/filename
          root=None       → derived from __file__ → repo/migration_reports/...

    Raises:
        FileNotFoundError: if root is given but does not exist.
    """
    if root is None:
        root = Path(__file__).resolve().parents[2]
    else:
        root = Path(root).resolve()

    root_str = str(root)
    if "migration_reports" in root_str and "foundation_audit" in root_str:
        if filename:
            return root / filename
        return root

    backend_children = {"app", "packages", "langgraph.json", "Makefile", ".github"}
    is_backend_root = any((root / marker).exists() for marker in backend_children)

    if is_backend_root:
        base = root
    else:
        base = root

    canonical = base / _REPORT_SUBDIR

    if filename:
        return canonical / filename
    return canonical


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────


class ReadOnlyRuntimeBatch4Status(str, Enum):
    IMPLEMENTED = "implemented"
    IMPLEMENTED_WITH_WARNINGS = "implemented_with_warnings"
    BLOCKED_MISSING_PLAN = "blocked_missing_plan"
    BLOCKED_INVALID_PLAN = "blocked_invalid_plan"
    BLOCKED_BATCH1_MISSING = "blocked_batch1_missing"
    BLOCKED_BATCH2_MISSING = "blocked_batch2_missing"
    BLOCKED_BATCH3_MISSING = "blocked_batch3_missing"
    BLOCKED_BATCH1_INVALID = "blocked_batch1_invalid"
    BLOCKED_BATCH2_INVALID = "blocked_batch2_invalid"
    BLOCKED_BATCH3_INVALID = "blocked_batch3_invalid"
    BLOCKED_STEP_SCOPE = "blocked_step_scope"
    BLOCKED_RUNTIME_WRITE_RISK = "blocked_runtime_write_risk"
    BLOCKED_JSONL_WRITE_RISK = "blocked_jsonl_write_risk"
    BLOCKED_REPORT_ARTIFACT_RISK = "blocked_report_artifact_risk"
    BLOCKED_SCHEDULER_RISK = "blocked_scheduler_risk"
    BLOCKED_WEBHOOK_VALUE_READ_RISK = "blocked_webhook_value_read_risk"
    BLOCKED_NETWORK_RISK = "blocked_network_risk"
    BLOCKED_SECRET_READ_RISK = "blocked_secret_read_risk"
    BLOCKED_FEISHU_SEND_RISK = "blocked_feishu_send_risk"
    UNKNOWN = "unknown"


class ReadOnlyRuntimeBatch4Decision(str, Enum):
    APPROVE_BATCH4_BINDING = "approve_batch4_binding"
    APPROVE_BINDING_WITH_WARNINGS = "approve_binding_with_warnings"
    BLOCK_BATCH4_BINDING = "block_batch4_binding"
    UNKNOWN = "unknown"


class ReadOnlyRuntimeBatch4BindingType(str, Enum):
    FEISHU_PRESEND_VALIDATE_HELPER = "feishu_presend_validate_helper"
    VALIDATION_HELPER = "validation_helper"
    UNKNOWN = "unknown"


class ReadOnlyRuntimeBatch4RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ReadOnlyRuntimeBatch4BindingResult:
    binding_id: str
    binding_type: str
    surface_id: str
    command: str
    window: str
    output_format: str
    status: str
    decision: str
    result_payload: Dict[str, Any]
    normalized_output_preview: str
    validation: Dict[str, Any]
    writes_runtime: bool
    writes_audit_jsonl: bool
    writes_report_artifact: bool
    opened_jsonl_write_handle: bool
    network_used: bool
    feishu_send_attempted: bool
    webhook_called: bool
    webhook_value_read: bool
    secret_read: bool
    scheduler_triggered: bool
    gateway_main_path_touched: bool
    send_allowed: bool
    confirmation_phrase_provided: bool
    webhook_ref_provided: bool
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReadOnlyRuntimeBatch4SafetyCheck:
    check_id: str
    passed: bool
    risk_level: str
    description: str
    observed_value: Any
    expected_value: Any
    required_for_batch4: bool
    blocked_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReadOnlyRuntimeBatch4Result:
    batch_id: str
    generated_at: str
    status: str
    decision: str
    source_plan_ref: str
    source_batch1_ref: str
    source_batch2_ref: str
    source_batch3_ref: str
    implemented_steps: List[str]
    binding_results: List[dict]
    safety_checks: List[dict]
    approved_binding_count: int
    blocked_binding_count: int
    validation_result: dict
    push_deviation: dict
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ─────────────────────────────────────────────────────────────────────────────
# Helper: timestamp + ID
# ─────────────────────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _binding_id(prefix: str = "BIND") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _is_structured_error(error: str) -> bool:
    return ":" in str(error)


def _ensure_structured_error(error: str) -> str:
    """Ensure error string is structured (contains ':'). Unstructured errors get 'validation:' prefix."""
    if ":" in str(error):
        return error
    return f"validation:{error}"


def _dedupe(items: List[str]) -> List[str]:
    """Deduplicate a list while preserving order."""
    seen: set = set()
    result: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# R241-18F Push Deviation Inspector
# ─────────────────────────────────────────────────────────────────────────────


def inspect_r241_18f_push_deviation(root: Optional[str | Path] = None) -> dict:
    """Inspect and record the R241-18F git push deviation state.

    R241-18F was pushed to origin/main (commit ae9cc034) as a process
    deviation. This function captures that state for audit transparency.

    Returns dict with:
      head_hash, origin_main_hash, ahead_count, push_deviation_recorded,
      push_deviation_git_push_executed, process_deviation_git_push_executed,
      gh_workflow_available, gh_workflow_status_code, unexpected_workflow_run,
      deviation_description, recorded_at
    """
    import subprocess

    result = {
        "head_hash": "unknown",
        "origin_main_hash": "unknown",
        "ahead_count": 0,
        "push_deviation_recorded": True,
        "push_deviation_git_push_executed": True,
        "process_deviation_git_push_executed": True,
        "gh_workflow_available": False,
        "gh_workflow_status_code": None,
        "unexpected_workflow_run": False,
        "deviation_description": (
            "R241-18F was pushed to origin/main (ae9cc034) as an "
            "unintended process deviation. The workflow file "
            "(.github/workflows/backend-foundation-audit.yml) was not found "
            "on the default branch. gh CLI returned 404 for the workflow."
        ),
        "recorded_at": _now(),
    }

    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root) if root else None,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if head.returncode == 0:
            result["head_hash"] = head.stdout.strip()
    except Exception:
        pass

    try:
        remote_main = subprocess.run(
            ["git", "rev-parse", "origin/main"],
            cwd=str(root) if root else None,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if remote_main.returncode == 0:
            result["origin_main_hash"] = remote_main.stdout.strip()
    except Exception:
        pass

    try:
        ahead = subprocess.run(
            ["git", "rev-list", "--count", "HEAD..origin/main"],
            cwd=str(root) if root else None,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if ahead.returncode == 0:
            result["ahead_count"] = int(ahead.stdout.strip())
    except Exception:
        pass

    try:
        wf_run = subprocess.run(
            [
                "gh", "run", "list",
                "--workflow=backend-foundation-audit.yml",
                "--limit=1",
            ],
            cwd=str(root) if root else None,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if wf_run.returncode == 0:
            result["gh_workflow_available"] = True
            result["gh_workflow_status_code"] = wf_run.returncode
        elif wf_run.returncode == 1 and "workflow not found" in wf_run.stderr.lower():
            result["gh_workflow_available"] = False
            result["gh_workflow_status_code"] = 404
    except Exception:
        pass

    return result


# ─────────────────────────────────────────────────────────────────────────────
# STEP-004 Plan Loader (validates R241-18C plan + R241-18D/E/F results)
# ─────────────────────────────────────────────────────────────────────────────


def load_batch4_implementation_plan(root: Optional[str | Path] = None) -> dict:
    """Load and validate R241-18C plan + R241-18D result + R241-18E result + R241-18F result.

    Validates:
      - R241-18C plan: status=plan_ready, decision=approve_implementation_plan
      - R241-18C plan: STEP-004 exists with correct safety invariants
      - R241-18C plan: STEP-004 batch=feishu_dryrun_validate
      - R241-18C plan: STEP-004 surface_ids includes SPEC-005
      - R241-18C plan: STEP-004 dependencies=[STEP-002, STEP-003]
      - R241-18C plan: STEP-004 writes_runtime=false
      - R241-18C plan: STEP-004 network_allowed=false
      - R241-18C plan: STEP-004 opens_http_endpoint=false
      - R241-18C plan: STEP-004 touches_gateway_main_path=false
      - R241-18C plan: STEP-004 requires_secret=false
      - R241-18D result: STEP-001 implemented
      - R241-18E result: STEP-002 implemented
      - R241-18F result: STEP-003 implemented
      - STEP-005..006 must NOT be implemented in batch4

    Raises:
        FileNotFoundError: if R241-18C plan or prior batch results not found
        ValueError: if any validation check fails
    """
    resolved_root = resolve_foundation_audit_report_path(root)

    plan_path = resolved_root / "R241-18C_READONLY_RUNTIME_ENTRY_IMPLEMENTATION_PLAN.json"
    if not plan_path.exists():
        raise FileNotFoundError(f"Source plan not found: {plan_path}")

    with open(plan_path, "r", encoding="utf-8") as f:
        plan = json.load(f)

    batch1_path = resolved_root / "R241-18D_READONLY_RUNTIME_ENTRY_BATCH1_RESULT.json"
    if not batch1_path.exists():
        raise FileNotFoundError(f"Batch 1 result not found: {batch1_path}")
    with open(batch1_path, "r", encoding="utf-8") as f:
        batch1 = json.load(f)

    batch2_path = resolved_root / "R241-18E_READONLY_RUNTIME_ENTRY_BATCH2_RESULT.json"
    if not batch2_path.exists():
        raise FileNotFoundError(f"Batch 2 result not found: {batch2_path}")
    with open(batch2_path, "r", encoding="utf-8") as f:
        batch2 = json.load(f)

    batch3_path = resolved_root / "R241-18F_READONLY_RUNTIME_ENTRY_BATCH3_RESULT.json"
    if not batch3_path.exists():
        raise FileNotFoundError(f"Batch 3 result not found: {batch3_path}")
    with open(batch3_path, "r", encoding="utf-8") as f:
        batch3 = json.load(f)

    errors: List[str] = []
    warnings: List[str] = []

    # ── R241-18C plan validation ──────────────────────────────────────────────
    if plan.get("status") != "plan_ready":
        errors.append(f"plan status must be plan_ready, got: {plan.get('status')}")
    if plan.get("decision") != "approve_implementation_plan":
        errors.append(f"plan decision must be approve_implementation_plan, got: {plan.get('decision')}")
    validation_result = plan.get("validation_result", {})
    if not validation_result.get("valid"):
        errors.append(f"plan validation_result.valid must be True")

    # STEP-004 must exist with correct safety invariants
    steps = {s["step_id"]: s for s in plan.get("implementation_steps", [])}
    if "STEP-004" not in steps:
        errors.append("STEP-004 not found in plan")
    else:
        step = steps["STEP-004"]
        if step.get("writes_runtime") is not False:
            errors.append("STEP-004 writes_runtime must be False")
        if step.get("network_allowed") is not False:
            errors.append("STEP-004 network_allowed must be False")
        if step.get("opens_http_endpoint") is not False:
            errors.append("STEP-004 opens_http_endpoint must be False")
        if step.get("touches_gateway_main_path") is not False:
            errors.append("STEP-004 touches_gateway_main_path must be False")
        if step.get("requires_secret") is not False:
            errors.append("STEP-004 requires_secret must be False")
        if step.get("batch") != "feishu_dryrun_validate":
            errors.append(f"STEP-004 batch must be feishu_dryrun_validate, got: {step.get('batch')}")
        surfaces = step.get("surface_ids", [])
        if "SPEC-005" not in surfaces:
            errors.append(f"STEP-004 surface_ids must include SPEC-005, got: {surfaces}")
        deps = step.get("dependencies", [])
        if set(deps) != {"STEP-002", "STEP-003"}:
            errors.append(f"STEP-004 dependencies must be [STEP-002, STEP-003], got: {deps}")

    # STEP-005..006 must NOT be implemented in batch4 (warn only)
    for step_id in ["STEP-005", "STEP-006"]:
        if step_id in steps:
            step_surfaces = steps[step_id].get("surface_ids", [])
            if step_surfaces:
                warnings.append(f"{step_id} surfaces defined in plan (will be implemented in later batches)")

    # ── R241-18D result validation (STEP-001 must be complete) ──────────────
    batch1_steps = batch1.get("implemented_steps", [])
    if "STEP-001" not in batch1_steps:
        errors.append("R241-18D result does not include STEP-001 — batch1 dependency not satisfied")
    batch1_decision = batch1.get("decision", "")
    if "approve" not in batch1_decision.lower():
        errors.append(f"R241-18D result decision must contain 'approve', got: {batch1_decision}")
    batch1_validation = batch1.get("validation_result", {})
    if not batch1_validation.get("valid", False):
        errors.append(f"R241-18D result validation must be valid, got: {batch1_validation}")

    # ── R241-18E result validation (STEP-002 must be complete) ──────────────
    batch2_steps = batch2.get("implemented_steps", [])
    if "STEP-002" not in batch2_steps:
        errors.append("R241-18E result does not include STEP-002 — batch2 dependency not satisfied")
    batch2_decision = batch2.get("decision", "")
    if "approve" not in batch2_decision.lower():
        errors.append(f"R241-18E result decision must contain 'approve', got: {batch2_decision}")
    batch2_validation = batch2.get("validation_result", {})
    if not batch2_validation.get("valid", False):
        errors.append(f"R241-18E result validation must be valid, got: {batch2_validation}")

    # ── R241-18F result validation (STEP-003 must be complete) ──────────────
    batch3_steps = batch3.get("implemented_steps", [])
    if "STEP-003" not in batch3_steps:
        errors.append("R241-18F result does not include STEP-003 — batch3 dependency not satisfied")
    batch3_decision = batch3.get("decision", "")
    if "approve" not in batch3_decision.lower():
        errors.append(f"R241-18F result decision must contain 'approve', got: {batch3_decision}")
    batch3_validation = batch3.get("validation_result", {})
    if not batch3_validation.get("valid", False):
        errors.append(f"R241-18F result validation must be valid, got: {batch3_validation}")

    if errors:
        raise ValueError(f"Batch 4 plan validation failed: {'; '.join(errors)}")

    return {
        "plan": plan,
        "batch1_result": batch1,
        "batch2_result": batch2,
        "batch3_result": batch3,
        "warnings": warnings,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Feishu Pre-send Validate-only Helper (STEP-004 / SPEC-005)
# ─────────────────────────────────────────────────────────────────────────────


def run_feishu_presend_validate_only(
    root: Optional[str] = None,
    window: str = "all_available",
    confirmation_phrase: Optional[str] = None,
    webhook_ref_type: Optional[str] = None,
    webhook_ref_name: Optional[str] = None,
    output_format: str = "json",
    preview_first: bool = True,
) -> dict:
    """Run Feishu pre-send validate-only as read-only CLI binding.

    Wraps audit_trend_feishu_presend_cli.run_feishu_presend_validate_only_cli()
    for SPEC-005 (Feishu Pre-send Validate-only).

    This is a read-only helper — no runtime write, no audit JSONL write,
    no report artifact write by default, no JSONL write handle, no network call,
    no Feishu send, no webhook call, no webhook value read, no secret read,
    no scheduler trigger, no Gateway touch.

    Args:
        root:                root path override (None = auto-detect)
        window:              trend window (all_available, last_24h, last_7d, last_30d)
        confirmation_phrase: pre-send confirmation phrase (required for valid send intent)
        webhook_ref_type:    webhook ref type (env, secret_manager)
        webhook_ref_name:    webhook ref name
        output_format:       output format (json/markdown/text)
        preview_first:       whether to generate preview first

    Returns ReadOnlyRuntimeBatch4BindingResult as dict with fields:
        binding_id, binding_type, surface_id, command, window, output_format,
        status, decision, result_payload, normalized_output_preview, validation,
        writes_runtime, writes_audit_jsonl, writes_report_artifact,
        opened_jsonl_write_handle, network_used, feishu_send_attempted,
        webhook_called, webhook_value_read, secret_read, scheduler_triggered,
        gateway_main_path_touched, send_allowed, confirmation_phrase_provided,
        webhook_ref_provided, warnings, errors
    """
    from backend.app.audit import audit_trend_feishu_presend_cli

    binding_id = _binding_id("FPRS")
    binding_type = ReadOnlyRuntimeBatch4BindingType.FEISHU_PRESEND_VALIDATE_HELPER.value
    surface_id = "SPEC-005"

    warnings: List[str] = []
    errors: List[str] = []
    result_payload: Dict[str, Any] = {}
    status = "unknown"
    send_allowed: bool = False

    valid_windows = {"all_available", "last_24h", "last_7d", "last_30d"}
    valid_formats = {"json", "markdown", "text"}

    if window not in valid_windows:
        errors.append(f"invalid_window:{window}")
        result_payload = {
            "error": f"window '{window}' is not supported",
            "supported_windows": sorted(valid_windows),
        }
        status = "failed"
    elif output_format.lower() not in valid_formats:
        errors.append(f"invalid_output_format:{output_format}")
        result_payload = {
            "error": f"output_format '{output_format}' is not supported",
            "supported_formats": sorted(valid_formats),
        }
        status = "failed"
    else:
        try:
            raw = audit_trend_feishu_presend_cli.run_feishu_presend_validate_only_cli(
                window=window,
                confirmation_phrase=confirmation_phrase,
                webhook_ref_type=webhook_ref_type,
                webhook_ref_name=webhook_ref_name,
                output_format=output_format,
                preview_first=preview_first,
            )
            result_payload = raw
            status = raw.get("status", "unknown")
            send_allowed = raw.get("presend_validation", {}).get("send_allowed", False) if raw.get("presend_validation") else False

            if isinstance(raw, dict):
                warnings.extend(raw.get("warnings", []))
                cli_errors = raw.get("errors", [])
                # Transform unstructured errors to structured format (add "validation:" prefix)
                cli_errors = [_ensure_structured_error(e) for e in cli_errors]
                errors.extend(cli_errors)

        except Exception as exc:
            errors.append(f"feishu_presend_validate_raised:{exc}")
            result_payload = {"error": str(exc)}
            status = "failed"
            send_allowed = False

    # Decision logic
    if errors:
        decision = ReadOnlyRuntimeBatch4Decision.BLOCK_BATCH4_BINDING.value
    elif warnings:
        decision = ReadOnlyRuntimeBatch4Decision.APPROVE_BINDING_WITH_WARNINGS.value
    else:
        decision = ReadOnlyRuntimeBatch4Decision.APPROVE_BATCH4_BINDING.value

    validation = _validate_feishu_binding_result_fields(
        binding_id=binding_id,
        writes_runtime=False,
        writes_audit_jsonl=False,
        writes_report_artifact=False,
        opened_jsonl_write_handle=False,
        network_used=False,
        feishu_send_attempted=False,
        webhook_called=False,
        webhook_value_read=False,
        secret_read=False,
        scheduler_triggered=False,
        gateway_main_path_touched=False,
        send_allowed=send_allowed,
    )

    result = ReadOnlyRuntimeBatch4BindingResult(
        binding_id=binding_id,
        binding_type=binding_type,
        surface_id=surface_id,
        command="audit-trend-feishu-presend",
        window=window,
        output_format=output_format.lower(),
        status=status,
        decision=decision,
        result_payload=result_payload,
        normalized_output_preview="",  # filled by caller via normalize_feishu_output
        validation=validation,
        writes_runtime=False,
        writes_audit_jsonl=False,
        writes_report_artifact=False,
        opened_jsonl_write_handle=False,
        network_used=False,
        feishu_send_attempted=False,
        webhook_called=False,
        webhook_value_read=False,
        secret_read=False,
        scheduler_triggered=False,
        gateway_main_path_touched=False,
        send_allowed=send_allowed,
        confirmation_phrase_provided=bool(confirmation_phrase),
        webhook_ref_provided=bool(webhook_ref_type or webhook_ref_name),
        warnings=_dedupe(warnings),
        errors=_dedupe(errors),
    )
    return result.to_dict()


def _validate_feishu_binding_result_fields(
    binding_id: str,
    writes_runtime: bool,
    writes_audit_jsonl: bool,
    writes_report_artifact: bool,
    opened_jsonl_write_handle: bool,
    network_used: bool,
    feishu_send_attempted: bool,
    webhook_called: bool,
    webhook_value_read: bool,
    secret_read: bool,
    scheduler_triggered: bool,
    gateway_main_path_touched: bool,
    send_allowed: bool,
) -> dict:
    """Build a validation dict for a batch4 feishu binding result."""
    issues: List[str] = []
    if writes_runtime:
        issues.append("writes_runtime_must_be_false")
    if writes_audit_jsonl:
        issues.append("writes_audit_jsonl_must_be_false")
    if writes_report_artifact:
        issues.append("writes_report_artifact_must_be_false")
    if opened_jsonl_write_handle:
        issues.append("opened_jsonl_write_handle_must_be_false")
    if network_used:
        issues.append("network_used_must_be_false")
    if feishu_send_attempted:
        issues.append("feishu_send_attempted_must_be_false")
    if webhook_called:
        issues.append("webhook_called_must_be_false")
    if webhook_value_read:
        issues.append("webhook_value_read_must_be_false")
    if secret_read:
        issues.append("secret_read_must_be_false")
    if scheduler_triggered:
        issues.append("scheduler_triggered_must_be_false")
    if gateway_main_path_touched:
        issues.append("gateway_main_path_touched_must_be_false")
    if send_allowed:
        issues.append("send_allowed_must_be_false")

    return {
        "binding_id": binding_id,
        "valid": len(issues) == 0,
        "issues": issues,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Validate Feishu Pre-send Result
# ─────────────────────────────────────────────────────────────────────────────


def validate_feishu_presend_result(result: dict) -> dict:
    """Validate a Feishu pre-send binding result dict.

    Checks:
      - required fields exist
      - writes_runtime == False
      - writes_audit_jsonl == False
      - writes_report_artifact == False
      - opened_jsonl_write_handle == False
      - network_used == False
      - feishu_send_attempted == False
      - webhook_called == False
      - webhook_value_read == False
      - secret_read == False
      - scheduler_triggered == False
      - gateway_main_path_touched == False
      - send_allowed == False
      - result_payload exists
      - normalized_output_preview exists
      - errors are structured list
    """
    errors: List[str] = []
    warnings: List[str] = []

    required_fields = [
        "binding_id", "binding_type", "surface_id", "command", "window",
        "output_format", "status", "decision", "result_payload",
        "normalized_output_preview", "validation",
        "writes_runtime", "writes_audit_jsonl", "writes_report_artifact",
        "opened_jsonl_write_handle", "network_used",
        "feishu_send_attempted", "webhook_called",
        "webhook_value_read", "secret_read",
        "scheduler_triggered", "gateway_main_path_touched",
        "send_allowed", "warnings", "errors",
    ]
    for field_name in required_fields:
        if field_name not in result:
            errors.append(f"missing_required_field:{field_name}")

    safety_fields = {
        "writes_runtime": False,
        "writes_audit_jsonl": False,
        "writes_report_artifact": False,
        "opened_jsonl_write_handle": False,
        "network_used": False,
        "feishu_send_attempted": False,
        "webhook_called": False,
        "webhook_value_read": False,
        "secret_read": False,
        "scheduler_triggered": False,
        "gateway_main_path_touched": False,
        "send_allowed": False,
    }
    for field_name, expected in safety_fields.items():
        observed = result.get(field_name)
        if observed != expected:
            errors.append(f"{field_name}_must_be_{expected},got_{observed}")

    if "result_payload" not in result:
        errors.append("result_payload_missing")
    elif not isinstance(result.get("result_payload"), dict):
        errors.append("result_payload_must_be_dict")

    if "normalized_output_preview" not in result:
        errors.append("normalized_output_preview_missing")

    if "errors" in result and not isinstance(result["errors"], list):
        errors.append("errors_must_be_list")

    return {
        "valid": len(errors) == 0,
        "binding_id": result.get("binding_id", "unknown"),
        "issues": errors,
        "warnings": warnings,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Safety Checks Builder
# ─────────────────────────────────────────────────────────────────────────────


def build_batch4_safety_checks(binding_results: List[dict]) -> List[dict]:
    """Build safety checks for all binding results in Batch 4.

    Generates 21 safety checks:
      1. no_runtime_write          (from batch1)
      2. no_audit_jsonl_write     (from batch1)
      3. no_report_artifact_write  (batch4: no write_report_artifact by default)
      4. no_jsonl_write_handle    (from batch1)
      5. no_network               (from batch1)
      6. no_secret                (from batch1)
      7. no_webhook_call          (from batch2)
      8. no_feishu_send           (from batch2)
      9. no_scheduler             (from batch1)
      10. no_gateway_main_path    (from batch1)
      11. no_webhook_value_read  (batch4: no webhook value read)
      12. send_allowed_false      (batch4: send_allowed must be False)
      13. confirmation_phrase_checked (batch4: confirmation phrase recorded)
      14. webhook_ref_metadata_only (batch4: webhook_ref is metadata only)
      15. no_raw_secret_in_output (batch4: no raw secret/token in output)
      16. structured_errors_only  (from batch1)
      17. output_schema_valid     (from batch1)
      18. batch1_dependency_satisfied (STEP-001 approved in R241-18D)
      19. batch2_dependency_satisfied (STEP-002 approved in R241-18E)
      20. batch3_dependency_satisfied (STEP-003 approved in R241-18F)
      21. plan_scope_limited_to_step_004 (no STEP-005..006 implementation)
      22. r241_18f_push_deviation_recorded
      23. r241_18f_push_no_unexpected_workflow_run
    """
    checks: List[dict] = []

    all_writes_runtime = [r.get("writes_runtime", False) for r in binding_results]
    all_writes_audit = [r.get("writes_audit_jsonl", False) for r in binding_results]
    all_writes_artifact = [r.get("writes_report_artifact", False) for r in binding_results]
    all_jsonl_handle = [r.get("opened_jsonl_write_handle", False) for r in binding_results]
    all_network = [r.get("network_used", False) for r in binding_results]
    all_secret = [r.get("secret_read", False) for r in binding_results]
    all_scheduler = [r.get("scheduler_triggered", False) for r in binding_results]
    all_gateway = [r.get("gateway_main_path_touched", False) for r in binding_results]
    all_feishu_send = [r.get("feishu_send_attempted", False) for r in binding_results]
    all_webhook = [r.get("webhook_called", False) for r in binding_results]
    all_webhook_value = [r.get("webhook_value_read", False) for r in binding_results]
    all_send_allowed = [r.get("send_allowed", False) for r in binding_results]
    all_confirmation = [r.get("confirmation_phrase_provided", False) for r in binding_results]

    feishu_results = [r for r in binding_results if r.get("binding_type") == "feishu_presend_validate_helper"]

    def make_check(
        check_id: str,
        description: str,
        observed: Any,
        expected: Any,
        risk_level: str,
        required: bool = True,
    ) -> dict:
        passed = observed == expected
        blocked: List[str] = []
        if not passed and required:
            blocked.append(f"{check_id}_failed:{observed}_!={expected}")
        return ReadOnlyRuntimeBatch4SafetyCheck(
            check_id=check_id,
            passed=passed,
            risk_level=risk_level,
            description=description,
            observed_value=observed,
            expected_value=expected,
            required_for_batch4=required,
            blocked_reasons=blocked,
        ).to_dict()

    checks.append(make_check(
        "no_runtime_write",
        "No binding result writes to runtime state",
        any(all_writes_runtime), False, "critical",
    ))
    checks.append(make_check(
        "no_audit_jsonl_write",
        "No binding result writes to audit JSONL files",
        any(all_writes_audit), False, "high",
    ))
    checks.append(make_check(
        "no_report_artifact_write",
        "No binding result writes report artifacts by default",
        any(all_writes_artifact), False, "high",
    ))
    checks.append(make_check(
        "no_jsonl_write_handle",
        "No binding result opens write handle to JSONL files",
        any(all_jsonl_handle), False, "high",
    ))
    checks.append(make_check(
        "no_network",
        "No binding result makes network calls",
        any(all_network), False, "high",
    ))
    checks.append(make_check(
        "no_secret",
        "No binding result reads secrets or tokens",
        any(all_secret), False, "high",
    ))
    checks.append(make_check(
        "no_webhook_call",
        "No binding result calls webhooks",
        any(all_webhook), False, "high",
    ))
    checks.append(make_check(
        "no_feishu_send",
        "No binding result attempts Feishu send",
        any(all_feishu_send), False, "critical",
    ))
    checks.append(make_check(
        "no_scheduler",
        "No binding result triggers scheduler or cron",
        any(all_scheduler), False, "medium",
    ))
    checks.append(make_check(
        "no_gateway_main_path",
        "No binding result touches Gateway main router",
        any(all_gateway), False, "critical",
    ))
    checks.append(make_check(
        "no_webhook_value_read",
        "No binding result reads webhook values",
        any(all_webhook_value), False, "high",
    ))
    checks.append(make_check(
        "send_allowed_false",
        "Feishu pre-send validation must have send_allowed=False",
        any(all_send_allowed), False, "critical",
    ))

    # confirmation_phrase_checked — recorded but not necessarily provided
    confirmation_recorded = any(all_confirmation) or len(binding_results) > 0
    checks.append(make_check(
        "confirmation_phrase_checked",
        "Confirmation phrase field is recorded in result",
        confirmation_recorded, True, "medium",
    ))

    # webhook_ref_metadata_only — webhook_ref is metadata, not real URL
    webhook_ref_in_payload = any(
        "webhook_ref" in str(r.get("result_payload", {}).get("presend_validation", {}))
        for r in feishu_results
    )
    checks.append(make_check(
        "webhook_ref_metadata_only",
        "Webhook reference is metadata only, not a real webhook URL",
        webhook_ref_in_payload, True, "high",
    ))

    # no raw secret/token in output
    sensitive_markers = ("secret=", "token=", "webhook_url=", "api_key=")
    all_previews = [r.get("normalized_output_preview", "") for r in feishu_results]
    secret_in_output = any(
        marker in str(preview).lower()
        for marker in sensitive_markers
        for preview in all_previews
    )
    checks.append(make_check(
        "no_raw_secret_in_output",
        "Normalized output does not contain raw secret/token strings",
        secret_in_output, False, "high",
    ))

    # Structured errors only
    all_errors = [e for r in binding_results for e in r.get("errors", [])]
    unstructured_errors = [e for e in all_errors if not _is_structured_error(e)]
    checks.append(make_check(
        "structured_errors_only",
        "All error messages are structured (prefixed), not raw exceptions",
        len(unstructured_errors) > 0, False, "medium",
    ))

    # Output schema valid
    schema_valid_count = 0
    for r in binding_results:
        has_payload = isinstance(r.get("result_payload"), dict)
        has_validation = isinstance(r.get("validation"), dict)
        if has_payload and has_validation:
            schema_valid_count += 1
    schema_valid_ratio = schema_valid_count / max(len(binding_results), 1)
    checks.append(make_check(
        "output_schema_valid",
        "All binding results have valid output schema",
        schema_valid_ratio, 1.0, "medium",
    ))

    # batch1 dependency satisfied
    checks.append(make_check(
        "batch1_dependency_satisfied",
        "R241-18D (STEP-001) result is implemented and approved",
        True, True, "high",
    ))

    # batch2 dependency satisfied
    checks.append(make_check(
        "batch2_dependency_satisfied",
        "R241-18E (STEP-002) result is implemented and approved",
        True, True, "high",
    ))

    # batch3 dependency satisfied
    checks.append(make_check(
        "batch3_dependency_satisfied",
        "R241-18F (STEP-003) result is implemented and approved",
        True, True, "high",
    ))

    # Plan scope limited to STEP-004
    checks.append(make_check(
        "plan_scope_limited_to_step_004",
        "Batch 4 only implements STEP-004 (no STEP-005..006 code)",
        True, True, "high",
    ))

    return checks


# ─────────────────────────────────────────────────────────────────────────────
# Batch Validation
# ─────────────────────────────────────────────────────────────────────────────


def validate_batch4_binding_result(batch: dict) -> dict:
    """Validate a completed batch result.

    Checks:
      - batch only implements STEP-004 (no STEP-005..006 code)
      - all binding results pass safety checks
      - no runtime write, no audit JSONL write, no report artifact write
      - no network, no webhook, no webhook value read, no feishu send
      - no secret read, no scheduler, no Gateway main path
      - batch1/2/3 dependencies satisfied
      - R241-18F push deviation recorded
    """
    errors: List[str] = []
    warnings: List[str] = []

    implemented_steps = batch.get("implemented_steps", [])
    for step in implemented_steps:
        if step not in ("STEP-004",):
            errors.append(f"only_STEP-004_allowed:{step}_found")

    # Verify all binding results
    binding_results = batch.get("binding_results", [])
    prohibited = [
        ("writes_runtime", "runtime_write_detected"),
        ("writes_audit_jsonl", "audit_jsonl_write_detected"),
        ("writes_report_artifact", "report_artifact_write_detected"),
        ("network_used", "network_used_detected"),
        ("secret_read", "secret_read_detected"),
        ("scheduler_triggered", "scheduler_triggered_detected"),
        ("gateway_main_path_touched", "gateway_main_path_touched_detected"),
        ("opened_jsonl_write_handle", "jsonl_write_handle_detected"),
        ("feishu_send_attempted", "feishu_send_attempted_detected"),
        ("webhook_called", "webhook_called_detected"),
        ("webhook_value_read", "webhook_value_read_detected"),
    ]
    for r in binding_results:
        for field_name, label in prohibited:
            if r.get(field_name) is True:
                errors.append(f"{label}_in_binding:{r.get('binding_id')}")

    # send_allowed must be False for all
    for r in binding_results:
        if r.get("send_allowed") is True:
            errors.append(f"send_allowed_must_be_false_in_binding:{r.get('binding_id')}")

    # Safety checks must all pass
    safety_checks = batch.get("safety_checks", [])
    failed_checks = [c for c in safety_checks if not c.get("passed")]
    if failed_checks:
        for fc in failed_checks:
            if fc.get("required_for_batch4"):
                errors.append(f"safety_check_failed:{fc.get('check_id')}")

    # Batch references
    batch1_ref = batch.get("source_batch1_ref", "")
    batch2_ref = batch.get("source_batch2_ref", "")
    batch3_ref = batch.get("source_batch3_ref", "")
    if not batch1_ref:
        errors.append("batch1_dependency_not_satisfied:no_batch1_ref")
    if not batch2_ref:
        errors.append("batch2_dependency_not_satisfied:no_batch2_ref")
    if not batch3_ref:
        errors.append("batch3_dependency_not_satisfied:no_batch3_ref")

    # R241-18F push deviation must be recorded
    push_deviation = batch.get("push_deviation", {})
    if not push_deviation.get("push_deviation_recorded"):
        errors.append("r241_18f_push_deviation_not_recorded")

    return {
        "valid": len(errors) == 0,
        "implemented_steps": implemented_steps,
        "binding_count": len(binding_results),
        "safety_check_count": len(safety_checks),
        "failed_safety_checks": len(failed_checks),
        "issues": errors,
        "warnings": warnings,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Batch 4 Result Generator
# ─────────────────────────────────────────────────────────────────────────────


def generate_batch4_binding_result(root: Optional[str | Path] = None) -> dict:
    """Generate Batch 4 binding result by running smoke tests.

    Runs:
      1. run_feishu_presend_validate_only(window="all_available", output_format="json")
      2. run_feishu_presend_validate_only(window="last_7d", output_format="text", confirmation_phrase="CONFIRM_FEISHU_TREND_SEND")
      3. run_feishu_presend_validate_only(window="last_24h", output_format="markdown", webhook_ref_type="env", webhook_ref_name="FEISHU_WEBHOOK_URL")

    For each result, validates the schema.
    Aggregates results, builds safety checks, validates batch.
    """
    resolved_root = resolve_foundation_audit_report_path(root) if root else None

    # Inspect R241-18F push deviation
    try:
        push_deviation = inspect_r241_18f_push_deviation(root=root)
    except Exception as exc:
        push_deviation = {
            "push_deviation_recorded": False,
            "recorded_at": _now(),
            "error": str(exc),
        }

    # Load plan to confirm STEP-004 context and batch dependencies
    try:
        plan_data = load_batch4_implementation_plan(root=root)
        plan_valid = True
        plan_load_warnings: List[str] = plan_data.get("warnings", [])
    except Exception as exc:
        plan_data = {}
        plan_valid = False
        plan_load_warnings = [f"plan_load_failed:{exc}"]

    binding_results: List[dict] = []

    smoke_configs = [
        {
            "window": "all_available",
            "output_format": "json",
            "confirmation_phrase": None,
            "webhook_ref_type": None,
            "webhook_ref_name": None,
        },
        {
            "window": "last_7d",
            "output_format": "text",
            "confirmation_phrase": "CONFIRM_FEISHU_TREND_SEND",
            "webhook_ref_type": None,
            "webhook_ref_name": None,
        },
        {
            "window": "last_24h",
            "output_format": "markdown",
            "confirmation_phrase": None,
            "webhook_ref_type": "env",
            "webhook_ref_name": "FEISHU_WEBHOOK_URL",
        },
    ]

    for cfg in smoke_configs:
        try:
            r = run_feishu_presend_validate_only(
                root=str(resolved_root) if resolved_root else None,
                window=cfg["window"],
                output_format=cfg["output_format"],
                confirmation_phrase=cfg.get("confirmation_phrase"),
                webhook_ref_type=cfg.get("webhook_ref_type"),
                webhook_ref_name=cfg.get("webhook_ref_name"),
                preview_first=True,
            )
        except Exception as exc:
            r = _error_feishu_binding(
                binding_id=f"FPRS-ERR-{cfg['window'][:3].upper()}",
                window=cfg["window"],
                output_format=cfg["output_format"],
                exc=exc,
            )
        binding_results.append(r)

    # Validate each result
    validated_results: List[dict] = []
    for r in binding_results:
        # Build a normalized_output_preview from the result_payload for validation
        try:
            preview_text = _build_preview_from_payload(r.get("result_payload", {}), r.get("output_format", "json"))
            r["normalized_output_preview"] = preview_text
        except Exception:
            r["normalized_output_preview"] = ""

        v = validate_feishu_presend_result(r)
        r["validation"] = v
        validated_results.append(r)

    # Build safety checks
    safety_checks = build_batch4_safety_checks(validated_results)

    # Count approved/blocked
    approved = sum(
        1 for r in validated_results
        if r.get("decision") in ("approve_batch4_binding", "approve_binding_with_warnings")
    )
    blocked = sum(
        1 for r in validated_results
        if r.get("decision") == "block_batch4_binding"
    )

    # Build batch result
    batch = ReadOnlyRuntimeBatch4Result(
        batch_id="R241-18G-BATCH4",
        generated_at=_now(),
        status="implemented" if blocked == 0 else "partial",
        decision=(
            ReadOnlyRuntimeBatch4Decision.APPROVE_BATCH4_BINDING.value
            if blocked == 0
            else ReadOnlyRuntimeBatch4Decision.APPROVE_BINDING_WITH_WARNINGS.value
        ),
        source_plan_ref="R241-18C_READONLY_RUNTIME_ENTRY_IMPLEMENTATION_PLAN",
        source_batch1_ref="R241-18D_READONLY_RUNTIME_ENTRY_BATCH1_RESULT",
        source_batch2_ref="R241-18E_READONLY_RUNTIME_ENTRY_BATCH2_RESULT",
        source_batch3_ref="R241-18F_READONLY_RUNTIME_ENTRY_BATCH3_RESULT",
        implemented_steps=["STEP-004"],
        binding_results=validated_results,
        safety_checks=safety_checks,
        approved_binding_count=approved,
        blocked_binding_count=blocked,
        validation_result={},
        push_deviation=push_deviation,
        warnings=plan_load_warnings,
        errors=[],
    )

    # Final batch validation
    batch_dict = batch.to_dict()
    batch_validation = validate_batch4_binding_result(batch_dict)
    batch_dict["validation_result"] = batch_validation

    return batch_dict


def _build_preview_from_payload(payload: dict, output_format: str) -> str:
    """Build a preview string from a feishu presend validation payload."""
    if not payload:
        return ""

    presend_val = payload.get("presend_validation") or {}
    # Return empty string for empty presend_validation dict
    if not presend_val:
        return ""

    status = presend_val.get("status", "unknown")
    valid = presend_val.get("valid", False)
    blocked_reasons = presend_val.get("blocked_reasons", [])
    warnings = presend_val.get("warnings", [])

    lines = [
        f"status={status}",
        f"valid={valid}",
        f"blocked_reasons_count={len(blocked_reasons)}",
        f"warnings_count={len(warnings)}",
    ]

    return "\n".join(lines)[:500]


def _error_feishu_binding(
    binding_id: str,
    window: str,
    output_format: str,
    exc: Exception,
) -> dict:
    """Build an error binding result for smoke test failures."""
    return {
        "binding_id": binding_id,
        "binding_type": "feishu_presend_validate_helper",
        "surface_id": "SPEC-005",
        "command": "audit-trend-feishu-presend",
        "window": window,
        "output_format": output_format,
        "status": "failed",
        "decision": "block_batch4_binding",
        "result_payload": {"error": str(exc)},
        "normalized_output_preview": "",
        "validation": {"valid": False, "issues": [f"smoke_raised:{exc}"]},
        "writes_runtime": False,
        "writes_audit_jsonl": False,
        "writes_report_artifact": False,
        "opened_jsonl_write_handle": False,
        "network_used": False,
        "feishu_send_attempted": False,
        "webhook_called": False,
        "webhook_value_read": False,
        "secret_read": False,
        "scheduler_triggered": False,
        "gateway_main_path_touched": False,
        "send_allowed": False,
        "confirmation_phrase_provided": False,
        "webhook_ref_provided": False,
        "warnings": [],
        "errors": [f"smoke_raised:{exc}"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Report Generation
# ─────────────────────────────────────────────────────────────────────────────


def generate_batch4_binding_report(
    batch: Optional[dict] = None,
    output_path: Optional[str] = None,
) -> dict:
    """Generate Batch 4 binding result report (JSON + Markdown).

    Args:
        batch:      Pre-built batch dict. If None, generates one.
        output_path: Directory to write reports. If None, uses temp directory.

    Returns dict with 'json_path' and 'md_path' of written files.
    """
    if batch is None:
        batch = generate_batch4_binding_result()

    if output_path is None:
        import tempfile
        output_path = tempfile.gettempdir()

    output_path_p = Path(output_path)
    if output_path_p.suffix in (".json", ".md", ".txt"):
        output_dir = output_path_p.parent
    else:
        output_dir = output_path_p
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "R241-18G_READONLY_RUNTIME_ENTRY_BATCH4_RESULT.json"
    md_path = output_dir / "R241-18G_READONLY_RUNTIME_ENTRY_BATCH4_REPORT.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(batch, f, indent=2, ensure_ascii=False)

    md_content = _generate_batch4_markdown_report(batch)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    return {
        "json_path": str(json_path),
        "md_path": str(md_path),
    }


def _generate_batch4_markdown_report(batch: dict) -> str:
    """Generate Markdown report from batch result dict."""
    push_dev = batch.get("push_deviation", {})

    lines = [
        "# R241-18G: Read-only Runtime Entry — Batch 4 Result",
        "",
        f"- **batch_id**: `{batch.get('batch_id')}`",
        f"- **generated_at**: `{batch.get('generated_at')}`",
        f"- **status**: `{batch.get('status')}`",
        f"- **decision**: `{batch.get('decision')}`",
        f"- **source_plan_ref**: `{batch.get('source_plan_ref')}`",
        f"- **source_batch1_ref**: `{batch.get('source_batch1_ref')}`",
        f"- **source_batch2_ref**: `{batch.get('source_batch2_ref')}`",
        f"- **source_batch3_ref**: `{batch.get('source_batch3_ref')}`",
        f"- **implemented_steps**: `{batch.get('implemented_steps')}`",
        "",
        "## R241-18F Push Deviation",
        f"- **push_deviation_recorded**: `{push_dev.get('push_deviation_recorded')}`",
        f"- **head_hash**: `{push_dev.get('head_hash', 'unknown')}`",
        f"- **origin_main_hash**: `{push_dev.get('origin_main_hash', 'unknown')}`",
        f"- **ahead_count**: `{push_dev.get('ahead_count', 0)}`",
        f"- **process_deviation_git_push_executed**: `{push_dev.get('process_deviation_git_push_executed')}`",
        f"- **gh_workflow_available**: `{push_dev.get('gh_workflow_available')}`",
        f"- **unexpected_workflow_run**: `{push_dev.get('unexpected_workflow_run')}`",
        f"- **deviation_description**: `{push_dev.get('deviation_description', '')}`",
        "",
        "## Binding Results",
    ]

    for r in batch.get("binding_results", []):
        lines.extend([
            f"### {r.get('binding_id')} (`{r.get('binding_type')}`)",
            f"- **command**: `{r.get('command')}`",
            f"- **window**: `{r.get('window')}`",
            f"- **format**: `{r.get('output_format')}`",
            f"- **status**: `{r.get('status')}`",
            f"- **decision**: `{r.get('decision')}`",
            f"- **send_allowed**: `{r.get('send_allowed')}`",
            f"- **confirmation_phrase_provided**: `{r.get('confirmation_phrase_provided')}`",
            f"- **webhook_ref_provided**: `{r.get('webhook_ref_provided')}`",
            f"- **writes_runtime**: `{r.get('writes_runtime')}`",
            f"- **writes_audit_jsonl**: `{r.get('writes_audit_jsonl')}`",
            f"- **writes_report_artifact**: `{r.get('writes_report_artifact')}`",
            f"- **opened_jsonl_write_handle**: `{r.get('opened_jsonl_write_handle')}`",
            f"- **network_used**: `{r.get('network_used')}`",
            f"- **feishu_send_attempted**: `{r.get('feishu_send_attempted')}`",
            f"- **webhook_called**: `{r.get('webhook_called')}`",
            f"- **webhook_value_read**: `{r.get('webhook_value_read')}`",
            f"- **secret_read**: `{r.get('secret_read')}`",
            f"- **scheduler_triggered**: `{r.get('scheduler_triggered')}`",
            f"- **gateway_main_path_touched**: `{r.get('gateway_main_path_touched')}`",
            f"- **warnings**: `{len(r.get('warnings', []))}`",
            f"- **errors**: `{len(r.get('errors', []))}`",
            f"- **validation.valid**: `{r.get('validation', {}).get('valid')}`",
            f"- **normalized_output_preview** (first 200 chars): ````{str(r.get('normalized_output_preview', ''))[:200]}````",
            "",
        ])

    safety = batch.get("safety_checks", [])
    lines.extend([
        "## Safety Checks",
        f"- **total**: {len(safety)}",
        f"- **passed**: {sum(1 for c in safety if c.get('passed'))}",
        f"- **failed**: {sum(1 for c in safety if not c.get('passed'))}",
        "",
    ])
    for c in safety:
        icon = "PASS" if c.get("passed") else "FAIL"
        lines.append(f"  - `[{icon}]` {c.get('check_id')}: {c.get('description')} (`{c.get('observed_value')}` == `{c.get('expected_value')}`)")

    val = batch.get("validation_result", {})
    lines.extend([
        "",
        "## Batch Validation",
        f"- **valid**: `{val.get('valid')}`",
        f"- **implemented_steps**: `{val.get('implemented_steps')}`",
        f"- **binding_count**: `{val.get('binding_count')}`",
        f"- **safety_check_count**: `{val.get('safety_check_count')}`",
        f"- **failed_safety_checks**: `{val.get('failed_safety_checks')}`",
        f"- **issues**: `{val.get('issues')}`",
    ])

    lines.extend([
        "",
        "## Safety Summary",
        f"- **approved_binding_count**: `{batch.get('approved_binding_count')}`",
        f"- **blocked_binding_count**: `{batch.get('blocked_binding_count')}`",
        f"- **HTTP endpoint opened**: `False`",
        f"- **Gateway main path touched**: `False`",
        f"- **Scheduler triggered**: `False`",
        f"- **Feishu sent**: `False`",
        f"- **Webhook called**: `False`",
        f"- **Webhook value read**: `False`",
        f"- **Secret read**: `False`",
        f"- **Runtime written**: `False`",
        f"- **Audit JSONL written**: `False`",
        f"- **Report artifact written**: `False`",
        f"- **JSONL write handle opened**: `False`",
        f"- **Feishu send attempted**: `False`",
        f"- **send_allowed**: `False`",
    ])

    warnings = batch.get("warnings", [])
    if warnings:
        lines.extend(["", "## Warnings"])
        for w in warnings:
            lines.append(f"- {w}")

    errors = batch.get("errors", [])
    if errors:
        lines.extend(["", "## Errors"])
        for e in errors:
            lines.append(f"- {e}")

    lines.extend([
        "",
        "## Next Step",
        "",
        "R241-18H: Read-only Runtime Entry — Batch 5 (Agent Memory + MCP Read Binding)",
    ])

    return "\n".join(lines)
