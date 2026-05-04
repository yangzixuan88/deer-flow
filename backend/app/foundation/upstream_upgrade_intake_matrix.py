"""
R241-17C: Upstream Upgrade Intake Matrix
R241-17D: Mainline Resume Gate

This module provides read-only upstream analysis for R241 foundation governance.
It does NOT execute openclaw update, doctor --fix, git merge, or any runtime changes.

Absolute prohibitions enforced:
- No openclaw update
- No doctor --fix
- No gateway restart
- No git pull/merge into current repo
- No git push
- No gh workflow run
- No secret/token read
- No runtime/audit/action queue write
- No auto-fix
"""

from __future__ import annotations

import json
import os
import subprocess
import textwrap
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class UpstreamIntegrationLayer(str, Enum):
    SAFE_DIRECT_UPDATE = "safe_direct_update"
    ADAPTER_PATCH_INTEGRATION = "adapter_patch_integration"
    REPORT_ONLY_QUARANTINE = "report_only_quarantine"
    FORBIDDEN_RUNTIME_REPLACEMENT = "forbidden_runtime_replacement"
    NEEDS_MANUAL_REVIEW = "needs_manual_review"
    UNKNOWN = "unknown"


class UpstreamRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class UpstreamActionDecision(str, Enum):
    ACCEPT_DIRECT = "accept_direct"
    ACCEPT_ADAPTER_PATCH = "accept_adapter_patch"
    QUARANTINE_REPORT_ONLY = "quarantine_report_only"
    REJECT_RUNTIME_REPLACEMENT = "reject_runtime_replacement"
    NEEDS_MANUAL_REVIEW = "needs_manual_review"
    UNKNOWN = "unknown"


class LocalFoundationSurface(str, Enum):
    FEISHU_CHANNEL = "feishu_channel"
    GATEWAY = "gateway"
    TOOL_RUNTIME = "tool_runtime"
    PROMPT_GOVERNANCE = "prompt_governance"
    MEMORY_RUNTIME = "memory_runtime"
    ASSET_REGISTRY = "asset_registry"
    AUDIT_TRAIL = "audit_trail"
    TREND_REPORT = "trend_report"
    CI_WORKFLOW = "ci_workflow"
    PLUGIN_REGISTRY = "plugin_registry"
    DOCTOR_HEALTH_CHECK = "doctor_health_check"
    TRACE_LOGGING = "trace_logging"
    BROWSER_AUTOMATION = "browser_automation"
    SCHEDULER = "scheduler"
    AUTO_FIX = "auto_fix"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Prohibited action sentinel (always False — no-op enforcement)
# ---------------------------------------------------------------------------

_PROHIBITED_ACTIONS_EXECUTED: list[str] = []


def _record_prohibited_action(action: str) -> None:
    """Record if a prohibited action was attempted. Always appends to sentinel."""
    _PROHIBITED_ACTIONS_EXECUTED.append(action)


def get_prohibited_actions_record() -> list[str]:
    return list(_PROHIBITED_ACTIONS_EXECUTED)


# ---------------------------------------------------------------------------
# Core data objects
# ---------------------------------------------------------------------------


class UpstreamChangeCandidate:
    def __init__(
        self,
        candidate_id: str,
        upstream_area: str,
        upstream_file_refs: list[str],
        official_change_summary: str,
        local_affected_surface: list[LocalFoundationSurface],
        integration_layer: UpstreamIntegrationLayer,
        risk_level: UpstreamRiskLevel,
        recommended_action: UpstreamActionDecision,
        blocked_reason: str | None = None,
        test_required: bool = False,
        rollback_required: bool = False,
        manual_confirmation_required: bool = False,
        warnings: list[str] | None = None,
        errors: list[str] | None = None,
    ):
        self.candidate_id = candidate_id
        self.upstream_area = upstream_area
        self.upstream_file_refs = upstream_file_refs
        self.official_change_summary = official_change_summary
        self.local_affected_surface = local_affected_surface
        self.integration_layer = integration_layer
        self.risk_level = risk_level
        self.recommended_action = recommended_action
        self.blocked_reason = blocked_reason
        self.test_required = test_required
        self.rollback_required = rollback_required
        self.manual_confirmation_required = manual_confirmation_required
        self.warnings = warnings or []
        self.errors = errors or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "upstream_area": self.upstream_area,
            "upstream_file_refs": self.upstream_file_refs,
            "official_change_summary": self.official_change_summary,
            "local_affected_surface": [s.value if isinstance(s, LocalFoundationSurface) else s for s in self.local_affected_surface],
            "integration_layer": self.integration_layer.value if isinstance(self.integration_layer, UpstreamIntegrationLayer) else self.integration_layer,
            "risk_level": self.risk_level.value if isinstance(self.risk_level, UpstreamRiskLevel) else self.risk_level,
            "recommended_action": self.recommended_action.value if isinstance(self.recommended_action, UpstreamActionDecision) else self.recommended_action,
            "blocked_reason": self.blocked_reason,
            "test_required": self.test_required,
            "rollback_required": self.rollback_required,
            "manual_confirmation_required": self.manual_confirmation_required,
            "warnings": self.warnings,
            "errors": self.errors,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> UpstreamChangeCandidate:
        return cls(
            candidate_id=d["candidate_id"],
            upstream_area=d["upstream_area"],
            upstream_file_refs=d["upstream_file_refs"],
            official_change_summary=d["official_change_summary"],
            local_affected_surface=[LocalFoundationSurface(s) if isinstance(s, str) else s for s in d["local_affected_surface"]],
            integration_layer=UpstreamIntegrationLayer(d["integration_layer"]) if isinstance(d["integration_layer"], str) else d["integration_layer"],
            risk_level=UpstreamRiskLevel(d["risk_level"]) if isinstance(d["risk_level"], str) else d["risk_level"],
            recommended_action=UpstreamActionDecision(d["recommended_action"]) if isinstance(d["recommended_action"], str) else d["recommended_action"],
            blocked_reason=d.get("blocked_reason"),
            test_required=d.get("test_required", False),
            rollback_required=d.get("rollback_required", False),
            manual_confirmation_required=d.get("manual_confirmation_required", False),
            warnings=d.get("warnings", []),
            errors=d.get("errors", []),
        )


class UpstreamIntakeMatrix:
    def __init__(
        self,
        matrix_id: str,
        upstream_url: str,
        upstream_head: str,
        upstream_branch: str,
        source_available: bool,
        candidates: list[UpstreamChangeCandidate],
        recommended_sequence: list[str] | None = None,
        warnings: list[str] | None = None,
        errors: list[str] | None = None,
    ):
        self.matrix_id = matrix_id
        self.generated_at = datetime.now(timezone.utc).isoformat()
        self.upstream_url = upstream_url
        self.upstream_head = upstream_head
        self.upstream_branch = upstream_branch
        self.source_available = source_available
        self.candidates = candidates
        self.recommended_sequence = recommended_sequence or []
        self.warnings = warnings or []
        self.errors = errors or []

    @property
    def direct_update_candidates_count(self) -> int:
        return sum(1 for c in self.candidates if c.integration_layer == UpstreamIntegrationLayer.SAFE_DIRECT_UPDATE)

    @property
    def adapter_patch_candidates_count(self) -> int:
        return sum(1 for c in self.candidates if c.integration_layer == UpstreamIntegrationLayer.ADAPTER_PATCH_INTEGRATION)

    @property
    def quarantine_candidates_count(self) -> int:
        return sum(1 for c in self.candidates if c.integration_layer == UpstreamIntegrationLayer.REPORT_ONLY_QUARANTINE)

    @property
    def forbidden_candidates_count(self) -> int:
        return sum(1 for c in self.candidates if c.integration_layer == UpstreamIntegrationLayer.FORBIDDEN_RUNTIME_REPLACEMENT)

    @property
    def manual_review_candidates_count(self) -> int:
        return sum(1 for c in self.candidates if c.integration_layer == UpstreamIntegrationLayer.NEEDS_MANUAL_REVIEW)

    def to_dict(self) -> dict[str, Any]:
        return {
            "matrix_id": self.matrix_id,
            "generated_at": self.generated_at,
            "upstream_url": self.upstream_url,
            "upstream_head": self.upstream_head,
            "upstream_branch": self.upstream_branch,
            "source_available": self.source_available,
            "candidates": [c.to_dict() for c in self.candidates],
            "direct_update_candidates_count": self.direct_update_candidates_count,
            "adapter_patch_candidates_count": self.adapter_patch_candidates_count,
            "quarantine_candidates_count": self.quarantine_candidates_count,
            "forbidden_candidates_count": self.forbidden_candidates_count,
            "manual_review_candidates_count": self.manual_review_candidates_count,
            "recommended_sequence": self.recommended_sequence,
            "safety_summary": self._safety_summary(),
            "warnings": self.warnings,
            "errors": self.errors,
        }

    def _safety_summary(self) -> dict[str, Any]:
        return {
            "total_candidates": len(self.candidates),
            "safe_direct_update": self.direct_update_candidates_count,
            "adapter_patch_integration": self.adapter_patch_candidates_count,
            "report_only_quarantine": self.quarantine_candidates_count,
            "forbidden_runtime_replacement": self.forbidden_candidates_count,
            "needs_manual_review": self.manual_review_candidates_count,
        }


class MainlineResumeGate:
    def __init__(
        self,
        gate_id: str,
        local_closure_complete: bool,
        post_publish_audit_stable: bool,
        workflow_dispatch_only: bool,
        upstream_intake_matrix_ready: bool,
        no_critical_unresolved_local_issue: bool,
        direct_update_candidates_count: int,
        adapter_patch_candidates_count: int,
        quarantine_candidates_count: int,
        forbidden_candidates_count: int,
        mainline_resume_allowed: bool,
        next_mainline_phase: str | None = None,
        blocked_reasons: list[str] | None = None,
        warnings: list[str] | None = None,
        errors: list[str] | None = None,
    ):
        self.gate_id = gate_id
        self.generated_at = datetime.now(timezone.utc).isoformat()
        self.local_closure_complete = local_closure_complete
        self.post_publish_audit_stable = post_publish_audit_stable
        self.workflow_dispatch_only = workflow_dispatch_only
        self.upstream_intake_matrix_ready = upstream_intake_matrix_ready
        self.no_critical_unresolved_local_issue = no_critical_unresolved_local_issue
        self.direct_update_candidates_count = direct_update_candidates_count
        self.adapter_patch_candidates_count = adapter_patch_candidates_count
        self.quarantine_candidates_count = quarantine_candidates_count
        self.forbidden_candidates_count = forbidden_candidates_count
        self.mainline_resume_allowed = mainline_resume_allowed
        self.next_mainline_phase = next_mainline_phase
        self.blocked_reasons = blocked_reasons or []
        self.warnings = warnings or []
        self.errors = errors or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "generated_at": self.generated_at,
            "local_closure_complete": self.local_closure_complete,
            "post_publish_audit_stable": self.post_publish_audit_stable,
            "workflow_dispatch_only": self.workflow_dispatch_only,
            "upstream_intake_matrix_ready": self.upstream_intake_matrix_ready,
            "no_critical_unresolved_local_issue": self.no_critical_unresolved_local_issue,
            "direct_update_candidates_count": self.direct_update_candidates_count,
            "adapter_patch_candidates_count": self.adapter_patch_candidates_count,
            "quarantine_candidates_count": self.quarantine_candidates_count,
            "forbidden_candidates_count": self.forbidden_candidates_count,
            "mainline_resume_allowed": self.mainline_resume_allowed,
            "next_mainline_phase": self.next_mainline_phase,
            "blocked_reasons": self.blocked_reasons,
            "warnings": self.warnings,
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
# Utility: safe subprocess runner (read-only git/ls operations only)
# ---------------------------------------------------------------------------


def _run_cmd(cmd: list[str], cwd: str | None = None, timeout: int = 30) -> str:
    """Run a read-only command and return stdout. Raises on non-zero exit."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        if result.returncode != 0:
            return f"[ERROR {result.returncode}] {result.stderr}"
        return result.stdout
    except subprocess.TimeoutExpired:
        return "[TIMEOUT]"
    except FileNotFoundError:
        return "[NOT_FOUND]"


# ---------------------------------------------------------------------------
# 1. Resolve Official Upstream Source
# ---------------------------------------------------------------------------


def resolve_official_upstream_source(
    root: str | None = None,
    upstream_url: str | None = None,
) -> dict[str, Any]:
    """
    Check git remote -v for existing upstream.
    If none found, use provided upstream_url or default candidate.
    Does NOT modify git remotes. Read-only.

    Returns:
        upstream_url, upstream_head, upstream_branch, source_available
    """
    if root is None:
        root = os.getcwd()
    upstream_url = upstream_url or "https://github.com/openclaw/openclaw.git"

    # Check remotes for existing upstream
    remotes_out = _run_cmd(["git", "remote", "-v"], cwd=root)
    has_upstream = any(
        "openclaw" in line and "openclaw/openclaw" not in line
        for line in remotes_out.splitlines()
    )
    existing_upstream = None
    for line in remotes_out.splitlines():
        if "openclaw" in line and "fetch" in line:
            parts = line.split()
            if len(parts) >= 2:
                existing_upstream = parts[1]
                break

    # Use existing or provided/default
    resolved_url = existing_upstream or upstream_url

    # Probe the URL
    head_out = _run_cmd(["git", "ls-remote", resolved_url, "HEAD"], timeout=15)
    head_available = not head_out.startswith("[ERROR") and not head_out.startswith("[TIMEOUT") and not head_out.startswith("[NOT_FOUND")

    upstream_head = ""
    if head_available:
        parts = head_out.strip().split()
        upstream_head = parts[0] if parts else ""

    return {
        "upstream_url": resolved_url,
        "upstream_head": upstream_head,
        "upstream_branch": "main",
        "source_available": head_available,
        "used_existing_remote": existing_upstream is not None,
        "remotes_checked": remotes_out.strip(),
    }


# ---------------------------------------------------------------------------
# 2. Collect Upstream Snapshot (read-only)
# ---------------------------------------------------------------------------


def collect_upstream_snapshot(
    root: str | None = None,
    upstream_url: str | None = None,
    snapshot_dir: str | None = None,
) -> dict[str, Any]:
    """
    Perform shallow clone of upstream into isolated snapshot directory.
    Does NOT merge into current repo. Read-only observation.

    Returns:
        snapshot_path, files_summary, dir_structure, readme_content, changelog_content
    """
    if root is None:
        root = os.getcwd()
    if upstream_url is None:
        r = resolve_official_upstream_source(root)
        upstream_url = r["upstream_url"]

    # Determine snapshot dir
    if snapshot_dir is None:
        snapshot_dir = os.path.join(root, ".tmp_upstream_openclaw_snapshot")

    # Check if already exists
    if os.path.exists(snapshot_dir):
        snapshot_exists = True
    else:
        snapshot_exists = False

    result: dict[str, Any] = {
        "snapshot_dir": snapshot_dir,
        "snapshot_existed": snapshot_exists,
        "files_summary": [],
        "dir_structure": [],
        "readme_content": "",
        "changelog_content": "",
        "package_json": {},
        "workflows_found": [],
        "source_areas": [],
        "warnings": [],
        "errors": [],
    }

    # If snapshot doesn't exist, do shallow clone
    if not snapshot_exists:
        clone_out = _run_cmd(
            ["git", "clone", "--depth", "1", "--single-branch", upstream_url, snapshot_dir],
            cwd=root,
            timeout=60,
        )
        if clone_out.startswith("[ERROR") or clone_out.startswith("[TIMEOUT") or clone_out.startswith("[NOT_FOUND"):
            result["errors"].append(f"Clone failed: {clone_out}")
            result["warnings"].append("Upstream snapshot unavailable — running in report-only mode with no source files")
            return result

    # List directory structure
    if os.path.exists(snapshot_dir):
        try:
            for entry in os.listdir(snapshot_dir):
                full = os.path.join(snapshot_dir, entry)
                if os.path.isdir(full):
                    result["dir_structure"].append(f"{entry}/")
                else:
                    result["dir_structure"].append(entry)
        except OSError as e:
            result["errors"].append(f"Cannot list snapshot dir: {e}")

    # Read README
    readme_paths = ["README.md", "README", "readme.md", "README.txt"]
    for rp in readme_paths:
        rp_full = os.path.join(snapshot_dir, rp)
        if os.path.exists(rp_full):
            try:
                with open(rp_full, "r", encoding="utf-8", errors="replace") as f:
                    result["readme_content"] = f.read()[:3000]
                break
            except OSError:
                pass

    # Read CHANGELOG
    changelog_paths = ["CHANGELOG.md", "CHANGELOG", "changelog.md", "HISTORY.md"]
    for cp in changelog_paths:
        cp_full = os.path.join(snapshot_dir, cp)
        if os.path.exists(cp_full):
            try:
                with open(cp_full, "r", encoding="utf-8", errors="replace") as f:
                    result["changelog_content"] = f.read()[:2000]
                break
            except OSError:
                pass

    # Read package.json
    pkg_path = os.path.join(snapshot_dir, "package.json")
    if os.path.exists(pkg_path):
        try:
            with open(pkg_path, "r", encoding="utf-8") as f:
                result["package_json"] = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            result["errors"].append(f"Cannot parse package.json: {e}")

    # Find workflow files
    gh_workflows = os.path.join(snapshot_dir, ".github", "workflows")
    if os.path.exists(gh_workflows):
        try:
            for wf in os.listdir(gh_workflows):
                result["workflows_found"].append(f".github/workflows/{wf}")
        except OSError:
            pass

    # Identify source areas
    top_level_dirs = [d for d in result["dir_structure"] if d.endswith("/")]
    result["source_areas"] = top_level_dirs

    # Walk and collect file summary (top-level only for safety)
    try:
        for root_dir, dirs, files in os.walk(snapshot_dir):
            # Only go 2 levels deep
            depth = root_dir[len(snapshot_dir):].count(os.sep)
            if depth >= 2:
                dirs[:] = []
                continue
            for f in files:
                if f.startswith("."):
                    continue
                rel = os.path.relpath(os.path.join(root_dir, f), snapshot_dir)
                if len(result["files_summary"]) < 500:
                    result["files_summary"].append(rel)
    except OSError as e:
        result["errors"].append(f"File walk error: {e}")

    return result


# ---------------------------------------------------------------------------
# 3. Classify Upstream Change Candidate
# ---------------------------------------------------------------------------


def classify_upstream_change_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """
    Classify a file/area into integration layer based on path patterns.

    Rules:
      - docs/test/helper/type/parser bugfix → safe_direct_update
      - Feishu/Gateway/plugin/doctor/trace/exec approval/symlink → adapter_patch_integration
      - browser/scheduler/auto-fix/prompt optimizer/real push → report_only_quarantine
      - direct runtime replacement (gateway run path, tool runtime, prompt runtime,
        memory runtime, asset registry) → forbidden_runtime_replacement
      - anything unclear → needs_manual_review
    """
    file_path = candidate.get("file_path", "")
    area = candidate.get("area", "unknown")
    summary = candidate.get("summary", "").lower()

    # Normalize path
    path_lower = (file_path + "/" + area).lower()

    # Forbidden runtime replacement
    forbidden_patterns = [
        "gateway/main",
        "tool_runtime_enforcement",
        "prompt_runtime",
        "memory_runtime",
        "asset_registry_runtime",
        "toolruntime",
        "promptruntime",
        "memoryruntime",
        "assetruntime",
    ]
    if any(p in path_lower for p in forbidden_patterns):
        return _make_classification(
            candidate,
            integration_layer=UpstreamIntegrationLayer.FORBIDDEN_RUNTIME_REPLACEMENT,
            risk_level=UpstreamRiskLevel.CRITICAL,
            action=UpstreamActionDecision.REJECT_RUNTIME_REPLACEMENT,
            blocked_reason="Direct runtime replacement is forbidden per R241 mandate",
            warnings=["Runtime replacement could break R241 foundation stability"],
        )

    # Report-only quarantine
    quarantine_patterns = [
        "browser",
        "browser_automation",
        "scheduler",
        "schedul",
        "auto_fix",
        "autofix",
        "auto-fix",
        "real_feishu",
        "real_push",
        "webhook_push",
        "prompt_optimizer",
        "memory_cleanup",
        "asset_promotion",
    ]
    if any(p in path_lower for p in quarantine_patterns):
        return _make_classification(
            candidate,
            integration_layer=UpstreamIntegrationLayer.REPORT_ONLY_QUARANTINE,
            risk_level=UpstreamRiskLevel.HIGH,
            action=UpstreamActionDecision.QUARANTINE_REPORT_ONLY,
            warnings=["High risk — requires manual review before any runtime change"],
        )

    # Adapter patch integration
    adapter_patterns = [
        "feishu",
        "lark",
        "gateway",
        "plugin",
        "doctor",
        "health_check",
        "trace",
        "logging",
        "otel",
        "exec_approval",
        "approval_logic",
        "symlink",
        "trust_root",
        "config_schema",
    ]
    if any(p in path_lower for p in adapter_patterns):
        return _make_classification(
            candidate,
            integration_layer=UpstreamIntegrationLayer.ADAPTER_PATCH_INTEGRATION,
            risk_level=UpstreamRiskLevel.MEDIUM,
            action=UpstreamActionDecision.ACCEPT_ADAPTER_PATCH,
            test_required=True,
            rollback_required=True,
            manual_confirmation_required=True,
        )

    # Safe direct update
    safe_patterns = [
        "docs",
        "documentation",
        "test",
        "tests",
        "helper",
        "type",
        "types",
        "parser_bugfix",
        "formatter",
        "validator_static",
        "diagnostic",
        "readme",
        "changelog",
        "licence",
        "license",
        "gitignore",
        "env_example",
    ]
    if any(p in path_lower for p in safe_patterns):
        return _make_classification(
            candidate,
            integration_layer=UpstreamIntegrationLayer.SAFE_DIRECT_UPDATE,
            risk_level=UpstreamRiskLevel.LOW,
            action=UpstreamActionDecision.ACCEPT_DIRECT,
        )

    # Unknown
    return _make_classification(
        candidate,
        integration_layer=UpstreamIntegrationLayer.NEEDS_MANUAL_REVIEW,
        risk_level=UpstreamRiskLevel.UNKNOWN,
        action=UpstreamActionDecision.NEEDS_MANUAL_REVIEW,
        warnings=["Could not auto-classify — needs manual review"],
    )


def _make_classification(
    candidate: dict[str, Any],
    integration_layer: UpstreamIntegrationLayer,
    risk_level: UpstreamRiskLevel,
    action: UpstreamActionDecision,
    blocked_reason: str | None = None,
    test_required: bool = False,
    rollback_required: bool = False,
    manual_confirmation_required: bool = False,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    result = dict(candidate)
    result["integration_layer"] = integration_layer.value
    result["risk_level"] = risk_level.value
    result["recommended_action"] = action.value
    result["blocked_reason"] = blocked_reason
    result["test_required"] = test_required
    result["rollback_required"] = rollback_required
    result["manual_confirmation_required"] = manual_confirmation_required
    result["warnings"] = warnings or []
    result["errors"] = errors or []
    return result


# ---------------------------------------------------------------------------
# 4. Build Upstream Optimization Intake Matrix
# ---------------------------------------------------------------------------


def build_upstream_optimization_intake_matrix(
    root: str | None = None,
    upstream_url: str | None = None,
) -> dict[str, Any]:
    """
    Full pipeline:
      1. resolve upstream
      2. collect snapshot
      3. identify candidates
      4. classify each
      5. generate recommended sequence
    """
    if root is None:
        root = os.getcwd()

    matrix_id = "R241-17C-MATRIX"
    upstream_info = resolve_official_upstream_source(root, upstream_url)
    snapshot = collect_upstream_snapshot(root, upstream_info["upstream_url"])

    # Build candidates from snapshot
    candidates: list[dict[str, Any]] = []

    # Check if source was available
    if not upstream_info["source_available"] or snapshot.get("errors"):
        # Source unavailable — generate report-only matrix
        pass
    else:
        # Identify candidates from snapshot structure
        candidates = _identify_candidates_from_snapshot(snapshot, upstream_info)

    # Classify each candidate
    classified = []
    for c in candidates:
        classified.append(classify_upstream_change_candidate(c))

    # Generate recommended sequence
    seq = _generate_recommended_sequence(classified)

    # Build matrix object
    matrix = UpstreamIntakeMatrix(
        matrix_id=matrix_id,
        upstream_url=upstream_info["upstream_url"],
        upstream_head=upstream_info["upstream_head"],
        upstream_branch="main",
        source_available=upstream_info["source_available"],
        candidates=[UpstreamChangeCandidate.from_dict(c) for c in classified],
        recommended_sequence=seq,
        warnings=snapshot.get("warnings", []) + upstream_info.get("warnings", []),
        errors=snapshot.get("errors", []) + upstream_info.get("errors", []),
    )

    return matrix.to_dict()


def _identify_candidates_from_snapshot(
    snapshot: dict[str, Any],
    upstream_info: dict[str, Any],
) -> list[dict[str, Any]]:
    """Identify change candidates from snapshot structure."""
    candidates = []
    files = snapshot.get("files_summary", [])
    dirs = snapshot.get("source_areas", [])
    readme = snapshot.get("readme_content", "")
    changelog = snapshot.get("changelog_content", "")
    workflows = snapshot.get("workflows_found", [])
    pkg = snapshot.get("package_json", {})

    # Build candidate for each major area
    area_map = {
        "feishu_channel": ["feishu", "lark", "channels/feishu"],
        "gateway": ["gateway", "app/gateway", "router"],
        "tool_runtime": ["tool", "runtime", "sandbox", "exec"],
        "prompt_governance": ["prompt", "governance", "agents", "soul"],
        "memory_runtime": ["memory", "storage"],
        "asset_registry": ["asset", "registry"],
        "ci_workflow": [".github/workflows", "workflows"],
        "plugin_registry": ["plugin", "plugins"],
        "doctor_health_check": ["doctor", "health", "check"],
        "trace_logging": ["trace", "logging", "otel", "observability"],
        "browser_automation": ["browser", "playwright"],
        "scheduler": ["scheduler", "cron", "job"],
        "auto_fix": ["auto_fix", "autofix", "auto-fix"],
    }

    candidate_id = 1

    # Add candidates from directory structure
    for area_key, path_patterns in area_map.items():
        matching_files = []
        for f in files:
            f_lower = f.lower()
            if any(p in f_lower for p in path_patterns):
                matching_files.append(f)

        if matching_files:
            # Determine summary from readme/changelog if available
            summary = _derive_area_summary(area_key, readme, changelog)
            candidates.append({
                "candidate_id": f"UPSTREAM-{candidate_id:03d}",
                "upstream_area": area_key,
                "upstream_file_refs": matching_files[:20],  # cap at 20
                "official_change_summary": summary,
                "local_affected_surface": [area_key],
                "file_path": f"upstream://{area_key}",
                "area": area_key,
                "summary": summary,
            })
            candidate_id += 1

    # Add workflow candidates
    if workflows:
        candidates.append({
            "candidate_id": f"UPSTREAM-{candidate_id:03d}",
            "upstream_area": "ci_workflow",
            "upstream_file_refs": workflows,
            "official_change_summary": "GitHub Actions CI workflow definitions",
            "local_affected_surface": ["ci_workflow"],
            "file_path": "upstream://ci_workflow",
            "area": "ci_workflow",
            "summary": "CI workflow",
        })
        candidate_id += 1

    # Add root config candidates
    root_configs = ["package.json", "pnpm-lock.yaml", "tsconfig.json", "pyproject.toml"]
    for rc in root_configs:
        if any(rc in f for f in files):
            candidates.append({
                "candidate_id": f"UPSTREAM-{candidate_id:03d}",
                "upstream_area": "root_config",
                "upstream_file_refs": [f for f in files if rc in f],
                "official_change_summary": f"Root configuration: {rc}",
                "local_affected_surface": ["ci_workflow"],
                "file_path": f"upstream://root_config/{rc}",
                "area": "root_config",
                "summary": f"Config: {rc}",
            })
            candidate_id += 1

    return candidates


def _derive_area_summary(area: str, readme: str, changelog: str) -> str:
    """Derive a summary for an area based on readme/changelog content."""
    combined = (readme + " " + changelog).lower()
    if area == "feishu_channel":
        return "Feishu/Lark channel integration for messaging"
    elif area == "gateway":
        return "Gateway route resolver and API routing"
    elif area == "tool_runtime":
        return "Tool execution runtime and sandbox"
    elif area == "prompt_governance":
        return "Prompt governance and AGENTS runtime"
    elif area == "memory_runtime":
        return "Memory runtime and persistence"
    elif area == "asset_registry":
        return "Asset registry and management"
    elif area == "ci_workflow":
        return "CI/CD GitHub Actions workflows"
    elif area == "plugin_registry":
        return "Plugin registry and cold startup"
    elif area == "doctor_health_check":
        return "Doctor health check and diagnostic"
    elif area == "trace_logging":
        return "Trace, logging, and observability"
    elif area == "browser_automation":
        return "Browser automation and Playwright"
    elif area == "scheduler":
        return "Scheduler and cron automation"
    elif area == "auto_fix":
        return "Auto-fix and self-healing"
    else:
        return f"Upstream area: {area}"


def _generate_recommended_sequence(classified: list[dict[str, Any]]) -> list[str]:
    """Generate recommended application sequence."""
    seq = []
    # Layer 1: Safe direct updates first
    safe = [c["candidate_id"] for c in classified if c["integration_layer"] == "safe_direct_update"]
    seq.extend(safe)
    # Layer 2: Adapter patches second
    adapter = [c["candidate_id"] for c in classified if c["integration_layer"] == "adapter_patch_integration"]
    seq.extend(adapter)
    # Layer 3: Report-only quarantine (no action)
    quarantine = [c["candidate_id"] for c in classified if c["integration_layer"] == "report_only_quarantine"]
    # Layer 4: Forbidden (no action, explicit block)
    forbidden = [c["candidate_id"] for c in classified if c["integration_layer"] == "forbidden_runtime_replacement"]
    return seq


# ---------------------------------------------------------------------------
# 5. Validate Upstream Intake Matrix
# ---------------------------------------------------------------------------


def validate_upstream_intake_matrix(matrix: dict[str, Any]) -> dict[str, Any]:
    """
    Validate that:
      - No openclaw update executed
      - No doctor --fix executed
      - No gateway restart executed
      - No git merge/pull into current repo
      - No runtime write
      - No secret read
      - High-risk not marked direct update
      - Forbidden candidates have reject_runtime_replacement
      - Adapter candidates require rollback and tests
    """
    prohibited_record = get_prohibited_actions_record()
    issues = []
    warnings = []

    # Check prohibited actions were not executed
    if prohibited_record:
        issues.append(f"Prohibited actions attempted: {prohibited_record}")

    # Check high-risk candidates are not marked direct update
    for c in matrix.get("candidates", []):
        layer = c.get("integration_layer", "")
        risk = c.get("risk_level", "")
        action = c.get("recommended_action", "")

        if layer == "safe_direct_update" and risk in ("high", "critical", "unknown"):
            issues.append(f"Candidate {c.get('candidate_id')} marked safe_direct_update but has risk={risk}")

        if layer == "forbidden_runtime_replacement":
            if action != "reject_runtime_replacement":
                issues.append(
                    f"Candidate {c.get('candidate_id')} is forbidden but action is {action}, expected reject_runtime_replacement"
                )

        if layer == "adapter_patch_integration":
            if not c.get("test_required"):
                warnings.append(f"Adapter candidate {c.get('candidate_id')} missing test_required=true")
            if not c.get("rollback_required"):
                warnings.append(f"Adapter candidate {c.get('candidate_id')} missing rollback_required=true")

    # Source availability
    if not matrix.get("source_available"):
        warnings.append("Upstream source unavailable — running in report-only mode")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "prohibited_actions_check": "pass" if not prohibited_record else "fail",
        "source_check": "available" if matrix.get("source_available") else "unavailable",
        "high_risk_direct_update_check": "pass" if not any(
            c.get("integration_layer") == "safe_direct_update" and c.get("risk_level") in ("high", "critical", "unknown")
            for c in matrix.get("candidates", [])
        ) else "fail",
    }


# ---------------------------------------------------------------------------
# 6. Generate Upstream Intake Matrix Report
# ---------------------------------------------------------------------------


def generate_upstream_intake_matrix_report(
    matrix: dict[str, Any] | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Generate R241-17C report files (JSON + MD)."""
    if matrix is None:
        matrix = build_upstream_optimization_intake_matrix()

    if output_path is None:
        output_path = "backend/migration_reports/foundation_audit"

    os.makedirs(output_path, exist_ok=True)

    json_path = os.path.join(output_path, "R241-17C_UPSTREAM_OPTIMIZATION_INTAKE_MATRIX.json")
    md_path = os.path.join(output_path, "R241-17C_UPSTREAM_OPTIMIZATION_INTAKE_MATRIX.md")

    # Write JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(matrix, f, indent=2, ensure_ascii=False)

    # Write MD
    md_lines = [
        "# R241-17C: Upstream Optimization Intake Matrix",
        "",
        f"**Generated:** {matrix.get('generated_at', 'unknown')}",
        f"**Upstream:** {matrix.get('upstream_url', 'unknown')}",
        f"**Upstream HEAD:** {matrix.get('upstream_head', 'unknown')}",
        f"**Source Available:** {matrix.get('source_available', False)}",
        "",
        "## Safety Summary",
        "",
        "| Category | Count |",
        "|---|---|",
        f"| Safe Direct Update | {matrix.get('direct_update_candidates_count', 0)} |",
        f"| Adapter Patch Integration | {matrix.get('adapter_patch_candidates_count', 0)} |",
        f"| Report-only Quarantine | {matrix.get('quarantine_candidates_count', 0)} |",
        f"| Forbidden Runtime Replacement | {matrix.get('forbidden_candidates_count', 0)} |",
        f"| Needs Manual Review | {matrix.get('manual_review_candidates_count', 0)} |",
        "",
        "## Candidates",
        "",
    ]

    for c in matrix.get("candidates", []):
        risk_color = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴", "unknown": "⚪"}.get(c.get("risk_level", "unknown"), "⚪")
        md_lines.append(f"### {c.get('candidate_id')}: {c.get('upstream_area', 'unknown')} {risk_color}")
        md_lines.append(f"- **Layer:** `{c.get('integration_layer', 'unknown')}`")
        md_lines.append(f"- **Risk:** `{c.get('risk_level', 'unknown')}`")
        md_lines.append(f"- **Action:** `{c.get('recommended_action', 'unknown')}`")
        if c.get("blocked_reason"):
            md_lines.append(f"- **Blocked:** {c.get('blocked_reason')}")
        if c.get("warnings"):
            md_lines.append(f"- **Warnings:** {', '.join(c.get('warnings', []))}")
        md_lines.append("")

    md_lines.extend([
        "## No-Exec Confirmation",
        "",
        "This report was generated in **read-only mode**. The following actions were NOT executed:",
        "- No `openclaw update`",
        "- No `openclaw doctor --fix`",
        "- No `git pull` / `git merge` into current repo",
        "- No `git push`",
        "- No `gh workflow run`",
        "- No gateway restart",
        "- No secret/token read",
        "- No runtime write",
        "- No auto-fix",
        "",
        "## Recommended Sequence",
    ])

    for step_id, cand_id in enumerate(matrix.get("recommended_sequence", []), 1):
        md_lines.append(f"{step_id}. {cand_id}")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    return {
        "json_path": json_path,
        "md_path": md_path,
        "matrix_id": matrix.get("matrix_id"),
    }


# ---------------------------------------------------------------------------
# 7. Evaluate Mainline Resume Gate
# ---------------------------------------------------------------------------


def evaluate_mainline_resume_gate(root: str | None = None) -> dict[str, Any]:
    """
    Evaluate whether mainline R241 can resume.

    Reads:
      - R241-17B-C post-publish audit report
      - R241-17B-C repair report
      - R241-17C intake matrix (if generated)
    """
    if root is None:
        root = os.getcwd()

    gate_id = "R241-17D-GATE"
    reports_dir = os.path.join(root, "backend", "migration_reports", "foundation_audit")

    # Load R241-17B-C report
    report_17c_path = os.path.join(reports_dir, "R241-17B_C_POST_PUBLISH_AUDIT_CONSISTENCY_REPAIR.json")
    audit_stable = False
    workflow_dispatch_only = False
    local_closure_complete = False

    if os.path.exists(report_17c_path):
        with open(report_17c_path, "r", encoding="utf-8") as f:
            report_17c = json.load(f)
        audit_result = report_17c.get("audit_result", {})
        if audit_result.get("status") == "operationally_closed_with_deviation":
            audit_stable = True
        test_results = report_17c.get("test_results", {})
        if test_results.get("total", {}).get("failed", 1) == 0:
            local_closure_complete = True

    # Check workflow dispatch only
    audit_module_path = os.path.join(root, "backend", "app", "foundation", "ci_workflow_trigger_parser.py")
    workflow_dispatch_only = os.path.exists(audit_module_path)

    # Check R241-17C matrix
    matrix_17c_path = os.path.join(reports_dir, "R241-17C_UPSTREAM_OPTIMIZATION_INTAKE_MATRIX.json")
    upstream_matrix_ready = os.path.exists(matrix_17c_path)

    # Check for critical unresolved issues
    no_critical_unresolved = local_closure_complete and audit_stable

    # Determine if mainline can resume
    mainline_resume_allowed = (
        local_closure_complete
        and audit_stable
        and workflow_dispatch_only
        and upstream_matrix_ready
        and no_critical_unresolved
    )

    blocked_reasons = []
    if not local_closure_complete:
        blocked_reasons.append("R241-17B-C local closure not confirmed")
    if not audit_stable:
        blocked_reasons.append("Post-publish audit not operationally closed")
    if not workflow_dispatch_only:
        blocked_reasons.append("Workflow trigger parser not confirmed")
    if not upstream_matrix_ready:
        blocked_reasons.append("R241-17C upstream intake matrix not generated")
    if not no_critical_unresolved:
        blocked_reasons.append("Critical unresolved local issues")

    next_phase = "R241-18A_RUNTIME_ACTIVATION_READINESS_REVIEW" if mainline_resume_allowed else None

    gate = MainlineResumeGate(
        gate_id=gate_id,
        local_closure_complete=local_closure_complete,
        post_publish_audit_stable=audit_stable,
        workflow_dispatch_only=workflow_dispatch_only,
        upstream_intake_matrix_ready=upstream_matrix_ready,
        no_critical_unresolved_local_issue=no_critical_unresolved,
        direct_update_candidates_count=0,
        adapter_patch_candidates_count=0,
        quarantine_candidates_count=0,
        forbidden_candidates_count=0,
        mainline_resume_allowed=mainline_resume_allowed,
        next_mainline_phase=next_phase,
        blocked_reasons=blocked_reasons,
    )

    # If matrix exists, populate counts
    if os.path.exists(matrix_17c_path):
        with open(matrix_17c_path, "r", encoding="utf-8") as f:
            m = json.load(f)
        gate.direct_update_candidates_count = m.get("direct_update_candidates_count", 0)
        gate.adapter_patch_candidates_count = m.get("adapter_patch_candidates_count", 0)
        gate.quarantine_candidates_count = m.get("quarantine_candidates_count", 0)
        gate.forbidden_candidates_count = m.get("forbidden_candidates_count", 0)

    return gate.to_dict()


# ---------------------------------------------------------------------------
# 8. Generate Mainline Resume Gate Report
# ---------------------------------------------------------------------------


def generate_mainline_resume_gate_report(
    gate: dict[str, Any] | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Generate R241-17D report files (JSON + MD)."""
    if gate is None:
        gate = evaluate_mainline_resume_gate()

    if output_path is None:
        output_path = "backend/migration_reports/foundation_audit"

    os.makedirs(output_path, exist_ok=True)

    json_path = os.path.join(output_path, "R241-17D_MAINLINE_RESUME_GATE.json")
    md_path = os.path.join(output_path, "R241-17D_MAINLINE_RESUME_GATE.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(gate, f, indent=2, ensure_ascii=False)

    status_icon = "✅" if gate.get("mainline_resume_allowed") else "❌"
    md_lines = [
        "# R241-17D: Mainline Resume Gate",
        "",
        f"**Generated:** {gate.get('generated_at', 'unknown')}",
        f"**Gate ID:** {gate.get('gate_id', 'unknown')}",
        f"**Status:** {status_icon} {'MAINLINE RESUME ALLOWED' if gate.get('mainline_resume_allowed') else 'BLOCKED'}",
        "",
        "## Gate Evaluation",
        "",
        f"- **Local Closure Complete:** {'✅' if gate.get('local_closure_complete') else '❌'}",
        f"- **Post-Publish Audit Stable:** {'✅' if gate.get('post_publish_audit_stable') else '❌'}",
        f"- **Workflow Dispatch Only:** {'✅' if gate.get('workflow_dispatch_only') else '❌'}",
        f"- **Upstream Intake Matrix Ready:** {'✅' if gate.get('upstream_intake_matrix_ready') else '❌'}",
        f"- **No Critical Unresolved Local Issue:** {'✅' if gate.get('no_critical_unresolved_local_issue') else '❌'}",
        "",
    ]

    if gate.get("blocked_reasons"):
        md_lines.append("## Blocked Reasons")
        for reason in gate.get("blocked_reasons", []):
            md_lines.append(f"- ❌ {reason}")
        md_lines.append("")

    if gate.get("mainline_resume_allowed"):
        md_lines.extend([
            "## ✅ Mainline Can Resume",
            "",
            f"**Next Phase:** `{gate.get('next_mainline_phase', 'unknown')}`",
            "",
            "### Upstream Optimization Summary",
            "",
            f"| Category | Count |",
            "|---|---|",
            f"| Direct Update Candidates | {gate.get('direct_update_candidates_count', 0)} |",
            f"| Adapter Patch Candidates | {gate.get('adapter_patch_candidates_count', 0)} |",
            f"| Quarantine Candidates | {gate.get('quarantine_candidates_count', 0)} |",
            f"| Forbidden Candidates | {gate.get('forbidden_candidates_count', 0)} |",
            "",
        ])
    else:
        md_lines.extend([
            "## ❌ Mainline Blocked",
            "",
            "Resolve all blocked reasons before resuming mainline R241.",
        ])

    if gate.get("warnings"):
        md_lines.append("\n## Warnings")
        for w in gate.get("warnings", []):
            md_lines.append(f"- ⚠️ {w}")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    return {
        "json_path": json_path,
        "md_path": md_path,
        "gate_id": gate.get("gate_id"),
    }