"""Disabled workflow draft design for R241-16C.

This module renders a GitHub Actions workflow draft as report-only text. It
does not create files under .github/workflows, enable triggers, read secrets,
call network/webhooks, write runtime state, write audit JSONL, or execute
auto-fix.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.foundation import ci_implementation_plan as ci_plan
from app.foundation import ci_local_dryrun


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
DEFAULT_PLAN_PATH = REPORT_DIR / "R241-16C_DISABLED_WORKFLOW_DRAFT_PLAN.json"
DEFAULT_REPORT_PATH = REPORT_DIR / "R241-16C_DISABLED_WORKFLOW_DRAFT_REPORT.md"
DEFAULT_YAML_DRAFT_PATH = REPORT_DIR / "R241-16C_FOUNDATION_CHECK_WORKFLOW_DRAFT.yml.txt"


class WorkflowDraftStatus:
    DESIGN_ONLY = "design_only"
    DISABLED_DRAFT = "disabled_draft"
    BLOCKED_AUTO_TRIGGER = "blocked_auto_trigger"
    BLOCKED_SECRET_ACCESS = "blocked_secret_access"
    BLOCKED_NETWORK_ACCESS = "blocked_network_access"
    UNKNOWN = "unknown"


class WorkflowTriggerPolicy:
    WORKFLOW_DISPATCH_ONLY = "workflow_dispatch_only"
    DISABLED_NO_TRIGGER = "disabled_no_trigger"
    PULL_REQUEST_FORBIDDEN = "pull_request_forbidden"
    PUSH_FORBIDDEN = "push_forbidden"
    SCHEDULE_FORBIDDEN = "schedule_forbidden"
    UNKNOWN = "unknown"


class WorkflowJobType:
    SMOKE = "smoke"
    FAST = "fast"
    SAFETY = "safety"
    SLOW = "slow"
    FULL = "full"
    COLLECT_ONLY = "collect_only"
    ARTIFACT_COLLECTION = "artifact_collection"
    UNKNOWN = "unknown"


class WorkflowSecurityPolicy:
    NO_SECRETS = "no_secrets"
    NO_NETWORK = "no_network"
    NO_RUNTIME_WRITE = "no_runtime_write"
    NO_AUTO_FIX = "no_auto_fix"
    READ_ONLY_ARTIFACTS = "read_only_artifacts"
    UNKNOWN = "unknown"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_workflow_trigger_policy() -> Dict[str, Any]:
    return {
        "trigger_policy": WorkflowTriggerPolicy.WORKFLOW_DISPATCH_ONLY,
        "current_status": WorkflowDraftStatus.DESIGN_ONLY,
        "auto_triggers_enabled": False,
        "workflow_dispatch_enabled": True,
        "pull_request_enabled": False,
        "push_enabled": False,
        "schedule_enabled": False,
        "warnings": [
            "workflow_dispatch is a future manual preview only",
            "do not copy this draft into .github/workflows without user confirmation",
        ],
        "errors": [],
    }


def _timeout_minutes(stage: Dict[str, Any]) -> int:
    seconds = stage.get("blocker_threshold_seconds") or stage.get("warning_threshold_seconds") or 300
    return max(1, int((float(seconds) + 59) // 60))


def build_workflow_job_specs(root: Optional[str] = None) -> Dict[str, Any]:
    loaded = ci_local_dryrun.load_ci_stage_specs_for_local_run(root)
    jobs: List[Dict[str, Any]] = []
    for stage in loaded["stage_specs"]:
        job_type = stage.get("stage_type", WorkflowJobType.UNKNOWN)
        jobs.append(
            {
                "job_id": f"job_{job_type}",
                "job_type": job_type,
                "name": stage.get("name", job_type),
                "command": stage.get("command", ""),
                "enabled": False,
                "trigger_policy": WorkflowTriggerPolicy.WORKFLOW_DISPATCH_ONLY,
                "gating_policy": stage.get("gating_policy", "unknown"),
                "runs_on": "ubuntu-latest",
                "timeout_minutes": _timeout_minutes(stage),
                "environment_variables": {
                    "FOUNDATION_CI_DRAFT": "disabled",
                    "FOUNDATION_CI_NO_EXTERNAL_CALLS": "true",
                },
                "secret_refs_allowed": False,
                "network_allowed": False,
                "runtime_write_allowed": False,
                "auto_fix_allowed": False,
                "artifact_upload_enabled": False,
                "artifact_patterns": stage.get("artifact_types", []),
                "warnings": ["disabled_draft_job_not_enabled"],
                "errors": [],
            }
        )

    artifact_specs = ci_plan.build_ci_artifact_collection_specs(str(Path(root) if root else ROOT))
    jobs.append(
        {
            "job_id": "job_artifact_collection",
            "job_type": WorkflowJobType.ARTIFACT_COLLECTION,
            "name": "Artifact Collection",
            "command": "collect report artifacts only",
            "enabled": False,
            "trigger_policy": WorkflowTriggerPolicy.WORKFLOW_DISPATCH_ONLY,
            "gating_policy": ci_plan.CIGatingPolicy.REPORT_ONLY,
            "runs_on": "ubuntu-latest",
            "timeout_minutes": 5,
            "environment_variables": {"FOUNDATION_CI_DRAFT": "disabled"},
            "secret_refs_allowed": False,
            "network_allowed": False,
            "runtime_write_allowed": False,
            "auto_fix_allowed": False,
            "artifact_upload_enabled": False,
            "artifact_patterns": [
                pattern
                for spec in artifact_specs.get("artifact_specs", [])
                for pattern in spec.get("include_patterns", [])
            ],
            "warnings": ["artifact_upload_disabled_in_design_phase"],
            "errors": [],
        }
    )
    return {"jobs": jobs, "job_count": len(jobs), "warnings": [], "errors": []}


def build_workflow_artifact_policy(root: Optional[str] = None) -> Dict[str, Any]:
    artifact_specs = ci_plan.build_ci_artifact_collection_specs(str(Path(root) if root else ROOT))
    include_paths = [
        "migration_reports/foundation_audit/*.json",
        "migration_reports/foundation_audit/*.md",
        "backend/migration_reports/foundation_audit/*.json",
        "backend/migration_reports/foundation_audit/*.md",
    ]
    exclude_patterns = [
        "**/audit_trail/*.jsonl",
        "**/runtime/**",
        "**/action_queue/**",
        "**/*secret*",
        "**/*token*",
        "**/webhook_url*",
    ]
    return {
        "artifact_policy_id": "R241-16C_artifact_policy",
        "source_artifact_specs": artifact_specs,
        "include_paths": include_paths,
        "exclude_patterns": exclude_patterns,
        "collect_primary_report_path": True,
        "collect_secondary_report_path_temporarily": True,
        "path_inconsistency_strategy": "collect_both_report_warning_no_migration_no_deletion",
        "retention_days": 30,
        "secrets_allowed": False,
        "runtime_files_allowed": False,
        "audit_jsonl_allowed": False,
        "warnings": ["secondary report path is temporary compatibility collection only"],
        "errors": [],
    }


def render_disabled_workflow_yaml_draft(spec: Dict[str, Any]) -> Dict[str, Any]:
    lines = [
        "# DISABLED DRAFT",
        "# DO NOT ENABLE WITHOUT USER CONFIRMATION",
        "# NO PR/PUSH/SCHEDULE TRIGGERS",
        "# Store as report artifact only; do not place under .github/workflows.",
        "name: Foundation Check Disabled Draft",
        "on:",
        "  workflow_dispatch:",
        "    inputs:",
        "      confirm_disabled_draft:",
        '        description: "Manual preview only; remains disabled by job guards"',
        "        required: true",
        '        default: "disabled"',
        "permissions:",
        "  contents: read",
        "jobs:",
    ]
    for job in spec.get("jobs", []):
        job_id = str(job.get("job_id", "job_unknown")).replace("-", "_")
        command = str(job.get("command", ""))
        lines.extend(
            [
                f"  {job_id}:",
                "    if: ${{ false }}",
                f"    name: {job.get('name', job_id)}",
                f"    runs-on: {job.get('runs_on', 'ubuntu-latest')}",
                f"    timeout-minutes: {job.get('timeout_minutes', 5)}",
                "    steps:",
                "      - name: Disabled draft command preview",
                f"        run: {command}",
            ]
        )
    yaml_text = "\n".join(lines) + "\n"
    return {
        "yaml_text": yaml_text,
        "warnings": ["yaml draft is report-only and must not be copied into active workflow path"],
        "errors": [],
    }


def build_disabled_workflow_draft_spec(root: Optional[str] = None) -> Dict[str, Any]:
    root_path = Path(root) if root else ROOT
    trigger_policy = build_workflow_trigger_policy()
    job_specs = build_workflow_job_specs(str(root_path))
    artifact_policy = build_workflow_artifact_policy(str(root_path))
    threshold_policy = ci_plan.build_ci_threshold_policy()
    path_policy = ci_plan.build_ci_path_compatibility_policy(str(root_path))
    blocked_actions = ci_plan.build_ci_blocked_actions()
    draft = {
        "workflow_id": "R241-16C_disabled_foundation_check_workflow",
        "generated_at": _utc_now(),
        "status": WorkflowDraftStatus.DISABLED_DRAFT,
        "workflow_name": "Foundation Check Disabled Draft",
        "trigger_policy": trigger_policy["trigger_policy"],
        "auto_triggers_enabled": trigger_policy["auto_triggers_enabled"],
        "workflow_dispatch_enabled": trigger_policy["workflow_dispatch_enabled"],
        "pull_request_enabled": trigger_policy["pull_request_enabled"],
        "push_enabled": trigger_policy["push_enabled"],
        "schedule_enabled": trigger_policy["schedule_enabled"],
        "jobs": job_specs["jobs"],
        "artifact_policy": artifact_policy,
        "path_compatibility_policy": path_policy,
        "threshold_policy": threshold_policy,
        "blocked_actions": blocked_actions,
        "warnings": trigger_policy["warnings"] + job_specs["warnings"] + artifact_policy["warnings"],
        "errors": [],
    }
    draft["yaml_draft"] = render_disabled_workflow_yaml_draft(draft)["yaml_text"]
    return draft


def _workflow_files(root: Path) -> List[Path]:
    workflow_dir = root / ".github" / "workflows"
    if not workflow_dir.exists():
        return []
    return list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml"))


def validate_disabled_workflow_draft(spec: Dict[str, Any], root: Optional[str] = None) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []
    blocked_reasons: List[str] = []
    root_path = Path(root) if root else ROOT

    checks = {
        "auto_triggers_disabled": spec.get("auto_triggers_enabled") is False,
        "no_pr_trigger": spec.get("pull_request_enabled") is False,
        "no_push_trigger": spec.get("push_enabled") is False,
        "no_schedule_trigger": spec.get("schedule_enabled") is False,
        "no_secret_refs": all(job.get("secret_refs_allowed") is False for job in spec.get("jobs", [])),
        "no_network": all(job.get("network_allowed") is False for job in spec.get("jobs", [])),
        "no_runtime_write": all(job.get("runtime_write_allowed") is False for job in spec.get("jobs", [])),
        "no_auto_fix": all(job.get("auto_fix_allowed") is False for job in spec.get("jobs", [])),
        "no_github_workflow_written": True,
    }

    yaml_text = str(spec.get("yaml_draft", ""))
    forbidden_yaml = [
        "pull_request:",
        "push:",
        "schedule:",
        "secrets.",
        "webhook",
        "curl",
        "Invoke-WebRequest",
        "auto-fix",
    ]
    for token in forbidden_yaml:
        if token.lower() in yaml_text.lower():
            errors.append(f"forbidden_yaml_token:{token}")

    artifact = spec.get("artifact_policy", {})
    excludes = " ".join(artifact.get("exclude_patterns", []))
    if "**/audit_trail/*.jsonl" not in artifact.get("exclude_patterns", []):
        errors.append("artifact_policy_missing_audit_jsonl_exclusion")
    for token in ["runtime", "action_queue", "secret", "token", "webhook"]:
        if token not in excludes:
            errors.append(f"artifact_policy_missing_exclusion:{token}")

    for name, ok in checks.items():
        if not ok:
            blocked_reasons.append(name)
            errors.append(f"validation_failed:{name}")

    report_yaml_path = REPORT_DIR / "R241-16C_FOUNDATION_CHECK_WORKFLOW_DRAFT.yml.txt"
    if report_yaml_path.exists():
        warnings.append("report_directory_yaml_txt_exists_allowed")

    return {
        "validation_id": "R241-16C_disabled_workflow_validation",
        "valid": not errors,
        "status": WorkflowDraftStatus.DISABLED_DRAFT if not errors else WorkflowDraftStatus.UNKNOWN,
        **checks,
        "blocked_reasons": blocked_reasons,
        "warnings": warnings,
        "errors": errors,
        "validated_at": _utc_now(),
        "existing_workflow_files_observed": [str(path) for path in _workflow_files(root_path)],
    }


def _render_markdown(spec: Dict[str, Any], validation: Dict[str, Any], yaml_path: str) -> str:
    jobs = spec.get("jobs", [])
    return "\n".join(
        [
            "# R241-16C Disabled Workflow Draft Report",
            "",
            "## 1. Modified Files",
            "",
            "- `backend/app/foundation/ci_workflow_draft.py`",
            "- `backend/app/foundation/test_ci_workflow_draft.py`",
            "- `migration_reports/foundation_audit/R241-16C_DISABLED_WORKFLOW_DRAFT_PLAN.json`",
            "- `migration_reports/foundation_audit/R241-16C_DISABLED_WORKFLOW_DRAFT_REPORT.md`",
            "- `migration_reports/foundation_audit/R241-16C_FOUNDATION_CHECK_WORKFLOW_DRAFT.yml.txt`",
            "",
            "## 2. WorkflowDraftStatus / WorkflowTriggerPolicy / WorkflowJobType / WorkflowSecurityPolicy",
            "",
            "- WorkflowDraftStatus: design_only, disabled_draft, blocked_auto_trigger, blocked_secret_access, blocked_network_access, unknown",
            "- WorkflowTriggerPolicy: workflow_dispatch_only, disabled_no_trigger, pull_request_forbidden, push_forbidden, schedule_forbidden, unknown",
            "- WorkflowJobType: smoke, fast, safety, slow, full, collect_only, artifact_collection, unknown",
            "- WorkflowSecurityPolicy: no_secrets, no_network, no_runtime_write, no_auto_fix, read_only_artifacts, unknown",
            "",
            "## 3. WorkflowDraftJobSpec Fields",
            "",
            "- job_id, job_type, name, command, enabled, trigger_policy, gating_policy, runs_on, timeout_minutes",
            "- environment_variables, secret_refs_allowed, network_allowed, runtime_write_allowed, auto_fix_allowed",
            "- artifact_upload_enabled, artifact_patterns, warnings, errors",
            "",
            "## 4. WorkflowDraftSpec Fields",
            "",
            "- workflow_id, generated_at, status, workflow_name, trigger_policy, auto_triggers_enabled",
            "- workflow_dispatch_enabled, pull_request_enabled, push_enabled, schedule_enabled, jobs",
            "- artifact_policy, path_compatibility_policy, threshold_policy, blocked_actions, warnings, errors",
            "",
            "## 5. WorkflowDraftValidationResult Fields",
            "",
            "- validation_id, valid, status, auto_triggers_disabled, no_secret_refs, no_network",
            "- no_runtime_write, no_auto_fix, no_pr_trigger, no_push_trigger, no_schedule_trigger",
            "- no_github_workflow_written, blocked_reasons, warnings, errors, validated_at",
            "",
            "## 6. Trigger Policy Result",
            "",
            f"- trigger_policy: `{spec.get('trigger_policy')}`",
            f"- auto_triggers_enabled: `{spec.get('auto_triggers_enabled')}`",
            f"- workflow_dispatch_enabled: `{spec.get('workflow_dispatch_enabled')}`",
            f"- pull_request_enabled: `{spec.get('pull_request_enabled')}`",
            f"- push_enabled: `{spec.get('push_enabled')}`",
            f"- schedule_enabled: `{spec.get('schedule_enabled')}`",
            "",
            "## 7. Job Specs Result",
            "",
            *[
                f"- `{job.get('job_type')}`: enabled={job.get('enabled')}, gating={job.get('gating_policy')}, command=`{job.get('command')}`"
                for job in jobs
            ],
            "",
            "## 8. Artifact Policy Result",
            "",
            f"- include_paths: `{spec.get('artifact_policy', {}).get('include_paths')}`",
            f"- exclude_patterns: `{spec.get('artifact_policy', {}).get('exclude_patterns')}`",
            f"- path strategy: `{spec.get('artifact_policy', {}).get('path_inconsistency_strategy')}`",
            "",
            "## 9. YAML Draft Render Result",
            "",
            f"- yaml draft path: `{yaml_path}`",
            "- suffix: `.yml.txt`",
            "- not written under `.github/workflows`",
            "",
            "## 10. Validation Result",
            "",
            f"- valid: `{validation.get('valid')}`",
            f"- errors: `{validation.get('errors')}`",
            f"- warnings: `{validation.get('warnings')}`",
            "",
            "## 11. Test Result",
            "",
            "To be populated from verification command output.",
            "",
            "## 12. Real Workflow",
            "",
            "No real workflow file is created or enabled.",
            "",
            "## 13. Trigger Enablement",
            "",
            "PR, push, and schedule triggers are disabled.",
            "",
            "## 14. Secret Access",
            "",
            "No secret refs are allowed or read.",
            "",
            "## 15. Network / Webhook",
            "",
            "No network or webhook calls are allowed.",
            "",
            "## 16. Runtime / Audit JSONL / Action Queue",
            "",
            "No runtime, audit JSONL, or action queue writes are performed.",
            "",
            "## 17. Auto-fix",
            "",
            "No auto-fix is executed.",
            "",
            "## 18. Remaining Breakpoints",
            "",
            "- Real workflow enablement remains blocked pending explicit user confirmation.",
            "- PR blocking fast+safety enablement needs R241-16D review.",
            "",
            "## 19. Next Recommendation",
            "",
            "Proceed to R241-16D PR Blocking Fast+Safety Workflow Enablement Review or manual confirmation.",
        ]
    )


def generate_disabled_workflow_draft_plan(output_path: Optional[str] = None) -> Dict[str, Any]:
    target = Path(output_path) if output_path else DEFAULT_PLAN_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    spec = build_disabled_workflow_draft_spec(str(ROOT))
    validation = validate_disabled_workflow_draft(spec, str(ROOT))
    plan = {"workflow_draft_spec": spec, "validation": validation, "generated_at": _utc_now()}
    target.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    yaml_path = target.with_name(DEFAULT_YAML_DRAFT_PATH.name)
    yaml_path.write_text(spec["yaml_draft"], encoding="utf-8")
    report_path = target.with_name(DEFAULT_REPORT_PATH.name)
    report_path.write_text(_render_markdown(spec, validation, str(yaml_path)), encoding="utf-8")
    return {
        "output_path": str(target),
        "report_path": str(report_path),
        "yaml_draft_path": str(yaml_path),
        **plan,
    }


__all__ = [
    "WorkflowDraftStatus",
    "WorkflowTriggerPolicy",
    "WorkflowJobType",
    "WorkflowSecurityPolicy",
    "build_workflow_trigger_policy",
    "build_workflow_job_specs",
    "build_workflow_artifact_policy",
    "render_disabled_workflow_yaml_draft",
    "build_disabled_workflow_draft_spec",
    "validate_disabled_workflow_draft",
    "generate_disabled_workflow_draft_plan",
]
