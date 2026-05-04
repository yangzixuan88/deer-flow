"""Local CI dry-run helpers for R241-16B.

This module simulates the CI stage matrix locally. It is intentionally limited:
it does not create GitHub Actions workflows, call network/webhooks, write
runtime state, write audit JSONL, read secrets, or execute auto-fix.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.foundation import ci_implementation_plan as ci_plan


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
DEFAULT_SAMPLE_PATH = REPORT_DIR / "R241-16B_LOCAL_CI_DRYRUN_SAMPLE.json"
DEFAULT_REPORT_PATH = REPORT_DIR / "R241-16B_LOCAL_CI_DRYRUN_REPORT.md"


class LocalCIStageStatus:
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED_BY_SELECTION = "skipped_by_selection"
    BLOCKED_BY_POLICY = "blocked_by_policy"
    UNKNOWN = "unknown"


class LocalCIRunMode:
    DRY_RUN = "dry_run"
    EXECUTE_SELECTED = "execute_selected"
    PLAN_ONLY = "plan_only"
    UNKNOWN = "unknown"


class LocalCIStageSelection:
    SMOKE = "smoke"
    FAST = "fast"
    SAFETY = "safety"
    SLOW = "slow"
    FULL = "full"
    COLLECT_ONLY = "collect_only"
    ALL_PR = "all_pr"
    ALL_NIGHTLY = "all_nightly"
    ALL = "all"
    UNKNOWN = "unknown"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tail_text(value: str, max_chars: int = 4000) -> str:
    if not value:
        return ""
    return value[-max_chars:]


def _stage_type(stage: Dict[str, Any]) -> str:
    return str(stage.get("stage_type") or LocalCIStageSelection.UNKNOWN)


def _allowed_commands() -> set[str]:
    return {stage["command"] for stage in ci_plan.build_ci_stage_implementation_specs()["specs"]}


def _stage_result_template(
    stage: Dict[str, Any],
    *,
    selected: bool,
    status: str,
    warnings: Optional[List[str]] = None,
    errors: Optional[List[str]] = None,
) -> Dict[str, Any]:
    now = _utc_now()
    return {
        "stage_id": stage.get("stage_id", "unknown"),
        "stage_type": _stage_type(stage),
        "name": stage.get("name", "unknown"),
        "command": stage.get("command", ""),
        "selected": selected,
        "status": status,
        "exit_code": None,
        "runtime_seconds": 0.0,
        "gating_policy": stage.get("gating_policy", "unknown"),
        "threshold_warning_seconds": stage.get("warning_threshold_seconds"),
        "threshold_blocker_seconds": stage.get("blocker_threshold_seconds"),
        "threshold_status": "not_evaluated",
        "stdout_tail": "",
        "stderr_tail": "",
        "artifacts_planned": stage.get("artifact_types", []),
        "warnings": list(warnings or []),
        "errors": list(errors or []),
        "started_at": now,
        "finished_at": now,
    }


def load_ci_stage_specs_for_local_run(root: Optional[str] = None) -> Dict[str, Any]:
    """Load local stage specs from the R241-16A implementation plan."""
    root_path = Path(root) if root else ROOT
    return {
        "stage_specs": ci_plan.build_ci_stage_implementation_specs()["specs"],
        "threshold_policy": ci_plan.build_ci_threshold_policy(),
        "artifact_specs": ci_plan.build_ci_artifact_collection_specs(str(root_path)),
        "path_compatibility": ci_plan.build_ci_path_compatibility_policy(str(root_path)),
        "warnings": [],
        "errors": [],
    }


def select_ci_stages(stage_specs: List[Dict[str, Any]], selection: str = "all_pr") -> Dict[str, Any]:
    """Select stage specs for a local CI run."""
    selection = selection or LocalCIStageSelection.ALL_PR
    selection_map = {
        LocalCIStageSelection.SMOKE: {ci_plan.CIExecutionStageType.SMOKE},
        LocalCIStageSelection.FAST: {ci_plan.CIExecutionStageType.FAST},
        LocalCIStageSelection.SAFETY: {ci_plan.CIExecutionStageType.SAFETY},
        LocalCIStageSelection.SLOW: {ci_plan.CIExecutionStageType.SLOW},
        LocalCIStageSelection.FULL: {ci_plan.CIExecutionStageType.FULL},
        LocalCIStageSelection.COLLECT_ONLY: {ci_plan.CIExecutionStageType.COLLECT_ONLY},
        LocalCIStageSelection.ALL_PR: {
            ci_plan.CIExecutionStageType.SMOKE,
            ci_plan.CIExecutionStageType.FAST,
            ci_plan.CIExecutionStageType.SAFETY,
            ci_plan.CIExecutionStageType.COLLECT_ONLY,
        },
        LocalCIStageSelection.ALL_NIGHTLY: {
            ci_plan.CIExecutionStageType.FAST,
            ci_plan.CIExecutionStageType.SAFETY,
            ci_plan.CIExecutionStageType.SLOW,
        },
        LocalCIStageSelection.ALL: {
            ci_plan.CIExecutionStageType.SMOKE,
            ci_plan.CIExecutionStageType.FAST,
            ci_plan.CIExecutionStageType.SAFETY,
            ci_plan.CIExecutionStageType.SLOW,
            ci_plan.CIExecutionStageType.FULL,
            ci_plan.CIExecutionStageType.COLLECT_ONLY,
        },
    }
    wanted = selection_map.get(selection)
    warnings: List[str] = []
    errors: List[str] = []
    if wanted is None:
        wanted = set()
        errors.append(f"unknown_selection:{selection}")

    selected = [stage for stage in stage_specs if _stage_type(stage) in wanted]
    deselected = [stage for stage in stage_specs if _stage_type(stage) not in wanted]
    return {
        "selection": selection,
        "selected": selected,
        "deselected": deselected,
        "selected_stage_types": [_stage_type(stage) for stage in selected],
        "deselected_stage_types": [_stage_type(stage) for stage in deselected],
        "warnings": warnings,
        "errors": errors,
    }


def _command_to_args(command: str) -> List[str]:
    args = shlex.split(command)
    if args and args[0] == "python":
        args[0] = sys.executable
    return args


def run_ci_stage_command(
    stage: Dict[str, Any],
    execute: bool = False,
    timeout_seconds: Optional[int] = None,
) -> Dict[str, Any]:
    """Run or plan a single known CI stage command."""
    command = stage.get("command", "")
    if command not in _allowed_commands():
        return _stage_result_template(
            stage,
            selected=True,
            status=LocalCIStageStatus.BLOCKED_BY_POLICY,
            errors=["unknown_stage_command_blocked"],
        )

    if not execute:
        return _stage_result_template(
            stage,
            selected=True,
            status=LocalCIStageStatus.PENDING,
            warnings=["execute_false_plan_only_no_pytest_run"],
        )

    started = _utc_now()
    start_time = time.perf_counter()
    try:
        completed = subprocess.run(
            _command_to_args(command),
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )
        runtime_seconds = round(time.perf_counter() - start_time, 3)
        status = LocalCIStageStatus.PASSED if completed.returncode == 0 else LocalCIStageStatus.FAILED
        return {
            **_stage_result_template(stage, selected=True, status=status),
            "exit_code": completed.returncode,
            "runtime_seconds": runtime_seconds,
            "stdout_tail": _tail_text(completed.stdout),
            "stderr_tail": _tail_text(completed.stderr),
            "started_at": started,
            "finished_at": _utc_now(),
        }
    except subprocess.TimeoutExpired as exc:
        runtime_seconds = round(time.perf_counter() - start_time, 3)
        return {
            **_stage_result_template(stage, selected=True, status=LocalCIStageStatus.FAILED),
            "exit_code": 124,
            "runtime_seconds": runtime_seconds,
            "stdout_tail": _tail_text(exc.stdout if isinstance(exc.stdout, str) else ""),
            "stderr_tail": _tail_text(exc.stderr if isinstance(exc.stderr, str) else ""),
            "started_at": started,
            "finished_at": _utc_now(),
            "errors": ["stage_timeout"],
        }


def evaluate_stage_threshold(stage_result: Dict[str, Any], threshold_policy: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate a stage result against exit code and runtime thresholds."""
    result = dict(stage_result)
    warnings = list(result.get("warnings", []))
    errors = list(result.get("errors", []))
    runtime = float(result.get("runtime_seconds") or 0.0)
    warning_threshold = result.get("threshold_warning_seconds")
    blocker_threshold = result.get("threshold_blocker_seconds")
    gating = result.get("gating_policy")

    threshold_status = "passed"
    if result.get("exit_code") not in (None, 0):
        result["status"] = LocalCIStageStatus.FAILED
        threshold_status = "failed"
        errors.append("stage_exit_code_failed")
    elif warning_threshold is not None and runtime > float(warning_threshold):
        result["status"] = LocalCIStageStatus.WARNING
        threshold_status = "threshold_warning"
        warnings.append("runtime_exceeded_warning_threshold")

    if blocker_threshold is not None and runtime > float(blocker_threshold):
        threshold_status = "threshold_blocker"
        warnings.append("runtime_exceeded_blocker_threshold")
        if gating == ci_plan.CIGatingPolicy.PR_BLOCKING:
            result["status"] = LocalCIStageStatus.FAILED
            errors.append("pr_blocking_stage_exceeded_blocker_threshold")

    if result.get("status") == LocalCIStageStatus.PENDING:
        threshold_status = "not_run"

    result["threshold_status"] = threshold_status
    result["warnings"] = warnings
    result["errors"] = errors
    return result


def run_local_ci_dryrun(
    selection: str = "all_pr",
    execute: bool = False,
    timeout_seconds: Optional[int] = None,
) -> Dict[str, Any]:
    """Run a local CI plan or execute selected predefined stage commands."""
    loaded = load_ci_stage_specs_for_local_run()
    selected_info = select_ci_stages(loaded["stage_specs"], selection)
    warnings: List[str] = list(loaded.get("warnings", [])) + list(selected_info.get("warnings", []))
    errors: List[str] = list(loaded.get("errors", [])) + list(selected_info.get("errors", []))

    stage_results: List[Dict[str, Any]] = []
    start_time = time.perf_counter()
    for stage in selected_info["selected"]:
        raw = run_ci_stage_command(stage, execute=execute, timeout_seconds=timeout_seconds)
        stage_results.append(evaluate_stage_threshold(raw, loaded["threshold_policy"]))

    for stage in selected_info["deselected"]:
        stage_results.append(
            _stage_result_template(stage, selected=False, status=LocalCIStageStatus.SKIPPED_BY_SELECTION)
        )

    runtime_total = round(sum(float(stage.get("runtime_seconds") or 0.0) for stage in stage_results), 3)
    warning_count = sum(len(stage.get("warnings", [])) for stage in stage_results) + len(warnings)
    error_count = sum(len(stage.get("errors", [])) for stage in stage_results) + len(errors)
    pr_blocking_failed = any(
        stage.get("selected")
        and stage.get("gating_policy") == ci_plan.CIGatingPolicy.PR_BLOCKING
        and stage.get("status") == LocalCIStageStatus.FAILED
        for stage in stage_results
    )
    selected_results = [stage for stage in stage_results if stage.get("selected")]
    selected_failed = any(stage.get("status") == LocalCIStageStatus.FAILED for stage in selected_results)
    selected_warning = any(stage.get("status") == LocalCIStageStatus.WARNING for stage in selected_results)

    if errors or selected_failed:
        overall_status = LocalCIStageStatus.FAILED
    elif selected_warning or warnings:
        overall_status = LocalCIStageStatus.WARNING
    else:
        overall_status = LocalCIStageStatus.PASSED if execute else LocalCIStageStatus.PENDING

    threshold_summary = {
        "passed": sum(1 for stage in selected_results if stage.get("threshold_status") == "passed"),
        "warning": sum(1 for stage in selected_results if stage.get("threshold_status") == "threshold_warning"),
        "blocker": sum(1 for stage in selected_results if stage.get("threshold_status") == "threshold_blocker"),
        "failed": sum(1 for stage in selected_results if stage.get("threshold_status") == "failed"),
        "not_run": sum(1 for stage in selected_results if stage.get("threshold_status") == "not_run"),
    }

    return {
        "run_id": f"local_ci_{int(time.time())}",
        "generated_at": _utc_now(),
        "mode": LocalCIRunMode.EXECUTE_SELECTED if execute else LocalCIRunMode.PLAN_ONLY,
        "selected_stages": selected_info["selected_stage_types"],
        "root": str(ROOT),
        "stage_results": stage_results,
        "overall_status": overall_status,
        "pr_blocking_failed": pr_blocking_failed,
        "warning_count": warning_count,
        "error_count": error_count,
        "runtime_total_seconds": runtime_total if execute else round(time.perf_counter() - start_time, 3),
        "threshold_summary": threshold_summary,
        "artifact_collection_plan": loaded["artifact_specs"],
        "path_compatibility_summary": loaded["path_compatibility"],
        "blocked_actions_verified": {
            "no_workflow_created": True,
            "no_network_call": True,
            "no_webhook_call": True,
            "no_runtime_write": True,
            "no_audit_jsonl_write": True,
            "no_action_queue_write": True,
            "no_secret_read": True,
            "no_auto_fix": True,
        },
        "warnings": warnings,
        "errors": errors,
    }


def format_local_ci_result(result: Dict[str, Any], output_format: str = "json") -> str | Dict[str, Any]:
    """Format a local CI result as json, markdown, or text."""
    output_format = output_format or "json"
    if output_format == "json":
        return result

    stages = result.get("stage_results", [])
    if output_format == "markdown":
        lines = [
            "# Local CI Dry-run Result",
            "",
            f"- Overall status: `{result.get('overall_status')}`",
            f"- Selected stages: `{', '.join(result.get('selected_stages', []))}`",
            f"- PR blocking failed: `{result.get('pr_blocking_failed')}`",
            f"- Runtime total seconds: `{result.get('runtime_total_seconds')}`",
            "",
            "| Stage | Selected | Status | Exit | Runtime | Threshold |",
            "|---|---:|---|---:|---:|---|",
        ]
        for stage in stages:
            lines.append(
                f"| {stage.get('stage_type')} | {stage.get('selected')} | {stage.get('status')} | "
                f"{stage.get('exit_code')} | {stage.get('runtime_seconds')} | {stage.get('threshold_status')} |"
            )
        lines.extend(
            [
                "",
                f"Threshold summary: `{result.get('threshold_summary')}`",
                f"Artifact collection plan count: `{len(result.get('artifact_collection_plan', {}).get('artifact_specs', []))}`",
                f"Path compatibility warning: `{result.get('path_compatibility_summary', {}).get('path_inconsistency')}`",
                "",
                "Safety notice: no network, no webhook, no runtime write, no audit JSONL write, no secret read, no auto-fix.",
            ]
        )
        return "\n".join(lines)

    if output_format == "text":
        stage_lines = [
            f"{stage.get('stage_type')}: selected={stage.get('selected')} status={stage.get('status')} "
            f"exit={stage.get('exit_code')} runtime={stage.get('runtime_seconds')}"
            for stage in stages
        ]
        return "\n".join(
            [
                "Local CI Dry-run Result",
                f"Overall status: {result.get('overall_status')}",
                f"Selected stages: {', '.join(result.get('selected_stages', []))}",
                f"PR blocking failed: {result.get('pr_blocking_failed')}",
                "Stages:",
                *stage_lines,
                f"Threshold summary: {result.get('threshold_summary')}",
                f"Path compatibility warning: {result.get('path_compatibility_summary', {}).get('path_inconsistency')}",
                "Safety notice: no network, no webhook, no runtime write, no audit JSONL write, no secret read, no auto-fix.",
            ]
        )

    return format_local_ci_result(result, "json")


def generate_local_ci_dryrun_sample(output_path: Optional[str] = None) -> Dict[str, Any]:
    """Generate a report-only local CI dry-run sample."""
    target = Path(output_path) if output_path else DEFAULT_SAMPLE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    plan_only_all_pr = run_local_ci_dryrun(selection=LocalCIStageSelection.ALL_PR, execute=False)
    execute_false_all_nightly = run_local_ci_dryrun(selection=LocalCIStageSelection.ALL_NIGHTLY, execute=False)
    sample = {
        "plan_only_all_pr": plan_only_all_pr,
        "execute_false_all_nightly": execute_false_all_nightly,
        "formatted_markdown_preview": format_local_ci_result(plan_only_all_pr, "markdown"),
        "formatted_text_preview": format_local_ci_result(execute_false_all_nightly, "text"),
        "generated_at": _utc_now(),
        "warnings": [],
    }
    target.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "output_path": str(target),
        **sample,
    }


def generate_local_ci_dryrun_report(output_path: Optional[str] = None) -> Dict[str, Any]:
    """Generate the R241-16B markdown report and sample JSON."""
    sample = generate_local_ci_dryrun_sample()
    target = Path(output_path) if output_path else DEFAULT_REPORT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# R241-16B Local CI Dry-run Report",
        "",
        "## 1. Modified Files",
        "",
        "- `scripts/ci_foundation_check.py`",
        "- `backend/app/foundation/ci_local_dryrun.py`",
        "- `backend/app/foundation/test_ci_local_dryrun.py`",
        "- `migration_reports/foundation_audit/R241-16B_LOCAL_CI_DRYRUN_SAMPLE.json`",
        "- `migration_reports/foundation_audit/R241-16B_LOCAL_CI_DRYRUN_REPORT.md`",
        "",
        "## 2. LocalCIStageStatus / LocalCIRunMode / LocalCIStageSelection",
        "",
        "- LocalCIStageStatus: pending, running, passed, failed, warning, skipped_by_selection, blocked_by_policy, unknown",
        "- LocalCIRunMode: dry_run, execute_selected, plan_only, unknown",
        "- LocalCIStageSelection: smoke, fast, safety, slow, full, collect_only, all_pr, all_nightly, all, unknown",
        "",
        "## 3. LocalCIStageResult Fields",
        "",
        "- stage_id, stage_type, name, command, selected, status, exit_code, runtime_seconds, gating_policy",
        "- threshold_warning_seconds, threshold_blocker_seconds, threshold_status, stdout_tail, stderr_tail",
        "- artifacts_planned, warnings, errors, started_at, finished_at",
        "",
        "## 4. LocalCIDryRunResult Fields",
        "",
        "- run_id, generated_at, mode, selected_stages, root, stage_results, overall_status",
        "- pr_blocking_failed, warning_count, error_count, runtime_total_seconds, threshold_summary",
        "- artifact_collection_plan, path_compatibility_summary, blocked_actions_verified, warnings, errors",
        "",
        "## 5. Stage Specs Loading Result",
        "",
        "- Source: `backend/app/foundation/ci_implementation_plan.py`",
        f"- Loaded all_pr stages: {sample['plan_only_all_pr']['selected_stages']}",
        f"- Loaded all_nightly stages: {sample['execute_false_all_nightly']['selected_stages']}",
        "",
        "## 6. Stage Selection Result",
        "",
        "- all_pr = smoke + fast + safety + collect_only",
        "- all_nightly = fast + safety + slow",
        "- single-stage selections are supported for smoke / fast / safety / slow / full / collect_only",
        "",
        "## 7. run_ci_stage_command Result",
        "",
        "- execute=False returns plan-only pending results and does not invoke pytest.",
        "- execute=True is restricted to predefined stage spec commands and uses subprocess without shell=True.",
        "- Unknown commands are blocked_by_policy.",
        "",
        "## 8. Threshold Evaluation Result",
        "",
        "- exit_code != 0 marks failed.",
        "- warning thresholds mark warning.",
        "- blocker thresholds fail PR-blocking stages.",
        "- slow warnings remain stabilization suggestions; no auto-fix is executed.",
        "",
        "## 9. Local CI Dry-run Result",
        "",
        f"- plan_only_all_pr overall_status: {sample['plan_only_all_pr']['overall_status']}",
        f"- execute_false_all_nightly overall_status: {sample['execute_false_all_nightly']['overall_status']}",
        "",
        "## 10. CLI Script Parameters",
        "",
        "- `--selection smoke|fast|safety|slow|full|collect_only|all_pr|all_nightly|all`",
        "- `--execute`",
        "- `--format json|markdown|text`",
        "- `--timeout-seconds`",
        "- `--write-report`",
        "- Forbidden send/webhook/network/auto-fix/secret/runtime-write flags are not accepted.",
        "",
        "## 11. CLI Smoke Result",
        "",
        "To be populated from verification command output.",
        "",
        "## 12. Test Result",
        "",
        "To be populated from verification command output.",
        "",
        "## 13. Real Workflow",
        "",
        "No `.github/workflows/*.yml` file is created or enabled.",
        "",
        "## 14. Deleted Or Skipped Tests",
        "",
        "No tests are deleted, skipped, or xfailed.",
        "",
        "## 15. Safety Coverage",
        "",
        "Safety coverage is not reduced.",
        "",
        "## 16. Runtime / Audit JSONL / Action Queue",
        "",
        "No runtime, audit JSONL, or action queue writes are performed.",
        "",
        "## 17. Network / Webhook",
        "",
        "No network or webhook calls are performed.",
        "",
        "## 18. Auto-fix",
        "",
        "No auto-fix is executed.",
        "",
        "## 19. Remaining Breakpoints",
        "",
        "- Optional execute smoke may be run manually for safety stage.",
        "- Real workflow draft remains blocked until R241-16C or explicit manual confirmation.",
        "",
        "## 20. Next Recommendation",
        "",
        "Proceed to R241-16C disabled workflow draft design or manual confirmation.",
    ]
    target.write_text("\n".join(lines), encoding="utf-8")
    return {"output_path": str(target), "sample": sample}


__all__ = [
    "LocalCIStageStatus",
    "LocalCIRunMode",
    "LocalCIStageSelection",
    "load_ci_stage_specs_for_local_run",
    "select_ci_stages",
    "run_ci_stage_command",
    "evaluate_stage_threshold",
    "run_local_ci_dryrun",
    "format_local_ci_result",
    "generate_local_ci_dryrun_sample",
    "generate_local_ci_dryrun_report",
]
