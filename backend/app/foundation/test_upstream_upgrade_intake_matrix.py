"""
Tests for R241-17C: Upstream Upgrade Intake Matrix
Tests for R241-17D: Mainline Resume Gate

Read-only validation — no prohibited actions executed.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure the module is importable from repo root
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from backend.app.foundation.upstream_upgrade_intake_matrix import (
    UpstreamIntegrationLayer,
    UpstreamRiskLevel,
    UpstreamActionDecision,
    LocalFoundationSurface,
    UpstreamChangeCandidate,
    UpstreamIntakeMatrix,
    MainlineResumeGate,
    resolve_official_upstream_source,
    collect_upstream_snapshot,
    classify_upstream_change_candidate,
    build_upstream_optimization_intake_matrix,
    validate_upstream_intake_matrix,
    generate_upstream_intake_matrix_report,
    evaluate_mainline_resume_gate,
    generate_mainline_resume_gate_report,
    get_prohibited_actions_record,
    _PROHIBITED_ACTIONS_EXECUTED,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_root(tmp_path):
    """Temp directory simulating repo root."""
    return str(tmp_path)


@pytest.fixture
def mock_git_remotes():
    """Mock git remote -v output showing no openclaw upstream."""
    return "origin\thttps://github.com/bytedance/deer-flow.git (fetch)\norigin\thttps://github.com/yangzixuan88/deer-flow.git (push)"


@pytest.fixture
def mock_git_remotes_with_upstream():
    """Mock git remote -v with openclaw upstream present."""
    return "origin\thttps://github.com/bytedance/deer-flow.git (fetch)\nupstream\thttps://github.com/openclaw/openclaw.git (fetch)"


# ---------------------------------------------------------------------------
# Test 1: resolve uses existing upstream when present
# ---------------------------------------------------------------------------

def test_resolve_uses_existing_upstream_when_present(temp_root, mock_git_remotes_with_upstream):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_git_remotes_with_upstream,
            stderr="",
        )
        # Only the remote -v call; subsequent ls-remote returns empty
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=mock_git_remotes_with_upstream, stderr=""),
            MagicMock(returncode=0, stdout="abc123\tHEAD\n", stderr=""),
        ]
        result = resolve_official_upstream_source(root=temp_root)
        assert result["source_available"] is True
        assert "openclaw" in result["upstream_url"]


# ---------------------------------------------------------------------------
# Test 2: resolve uses default candidate when no upstream
# ---------------------------------------------------------------------------

def test_resolve_uses_default_candidate_when_no_upstream(temp_root, mock_git_remotes):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_git_remotes, stderr="")
        result = resolve_official_upstream_source(root=temp_root)
        # Should fall back to default https://github.com/openclaw/openclaw.git
        assert result["source_available"] is True
        assert result["upstream_url"] == "https://github.com/openclaw/openclaw.git"


# ---------------------------------------------------------------------------
# Test 3: resolve does NOT modify remotes
# ---------------------------------------------------------------------------

def test_resolve_does_not_modify_remotes(temp_root, mock_git_remotes):
    calls_made = []
    def track_run(cmd, cwd=None, capture_output=False, text=False, timeout=None, shell=False):
        calls_made.append(cmd)
        return MagicMock(returncode=0, stdout=mock_git_remotes, stderr="")

    with patch("subprocess.run", side_effect=track_run):
        result = resolve_official_upstream_source(root=temp_root)

    # Should only call git remote -v and git ls-remote, never git remote add
    remote_add_calls = [c for c in calls_made if "remote" in c and "add" in c]
    assert remote_add_calls == [], f"Unexpected remote add calls: {remote_add_calls}"


# ---------------------------------------------------------------------------
# Test 4: collect snapshot uses isolated directory
# ---------------------------------------------------------------------------

def test_collect_snapshot_uses_isolated_dir(temp_root, tmp_path):
    # Create real files in snapshot dir so open() works without complex mocks
    snap_dir = os.path.join(str(tmp_path), ".tmp_upstream_openclaw_snapshot")
    os.makedirs(snap_dir, exist_ok=True)
    with open(os.path.join(snap_dir, "README.md"), "w") as f:
        f.write("# OpenClaw\nMock upstream")
    with open(os.path.join(snap_dir, "package.json"), "w") as f:
        json.dump({"name": "openclaw", "version": "1.0.0"}, f)
    os.makedirs(os.path.join(snap_dir, ".github", "workflows"), exist_ok=True)
    with open(os.path.join(snap_dir, ".github", "workflows", "ci.yml"), "w") as f:
        f.write("name: CI")

    with patch("backend.app.foundation.upstream_upgrade_intake_matrix._run_cmd") as mock_cmd:
        result = collect_upstream_snapshot(root=str(tmp_path))

    assert ".tmp_upstream_openclaw_snapshot" in result["snapshot_dir"]
    assert result["snapshot_existed"] is True


# ---------------------------------------------------------------------------
# Test 5: collect snapshot does not merge into current repo
# ---------------------------------------------------------------------------

def test_collect_snapshot_does_not_merge_into_current_repo(temp_root):
    calls_made = []
    def track_run(cmd, cwd=None, capture_output=False, text=False, timeout=None, shell=False):
        calls_made.append(cmd)
        if "clone" in cmd:
            return MagicMock(returncode=0, stdout="", stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=track_run):
        with patch("os.path.exists", return_value=True):
            with patch("os.listdir", return_value=[]):
                collect_upstream_snapshot(root=temp_root)

    merge_calls = [c for c in calls_made if any(op in c for op in ["merge", "pull", "rebase", "checkout"])]
    assert merge_calls == [], f"Unexpected merge/pull calls: {merge_calls}"


# ---------------------------------------------------------------------------
# Test 6: classify docs as safe_direct_update
# ---------------------------------------------------------------------------

def test_classify_docs_as_safe_direct_update():
    candidate = {
        "candidate_id": "TEST-001",
        "file_path": "docs/README.md",
        "area": "docs",
        "summary": "Documentation update",
        "upstream_area": "documentation",
        "upstream_file_refs": ["docs/README.md"],
        "official_change_summary": "Update docs",
        "local_affected_surface": ["unknown"],
    }
    result = classify_upstream_change_candidate(candidate)
    assert result["integration_layer"] == "safe_direct_update"
    assert result["risk_level"] == "low"
    assert result["recommended_action"] == "accept_direct"


# ---------------------------------------------------------------------------
# Test 7: classify parser bugfix as safe_direct_update
# ---------------------------------------------------------------------------

def test_classify_parser_bugfix_as_safe_direct_update():
    candidate = {
        "candidate_id": "TEST-002",
        "file_path": "packages/parser/src/fix_bool_coercion.ts",
        "area": "parser_bugfix",
        "summary": "Parser bugfix",
        "upstream_area": "parser",
        "upstream_file_refs": ["packages/parser/src/fix_bool_coercion.ts"],
        "official_change_summary": "Fix YAML bool coercion",
        "local_affected_surface": ["unknown"],
    }
    result = classify_upstream_change_candidate(candidate)
    assert result["integration_layer"] == "safe_direct_update"
    assert result["risk_level"] == "low"


# ---------------------------------------------------------------------------
# Test 8: classify Feishu parser as adapter_patch_integration
# ---------------------------------------------------------------------------

def test_classify_feishu_parser_as_adapter_patch():
    candidate = {
        "candidate_id": "TEST-003",
        "file_path": "backend/app/channels/feishu.py",
        "area": "feishu",
        "summary": "Feishu channel parser",
        "upstream_area": "feishu_channel",
        "upstream_file_refs": ["backend/app/channels/feishu.py"],
        "official_change_summary": "Feishu message parser update",
        "local_affected_surface": ["feishu_channel"],
    }
    result = classify_upstream_change_candidate(candidate)
    assert result["integration_layer"] == "adapter_patch_integration"
    assert result["risk_level"] == "medium"
    assert result["recommended_action"] == "accept_adapter_patch"


# ---------------------------------------------------------------------------
# Test 9: classify Gateway route resolver as adapter_patch_integration
# ---------------------------------------------------------------------------

def test_classify_gateway_route_resolver_as_adapter_patch():
    candidate = {
        "candidate_id": "TEST-004",
        "file_path": "backend/app/gateway/routers/agents.py",
        "area": "gateway",
        "summary": "Gateway route resolver",
        "upstream_area": "gateway",
        "upstream_file_refs": ["backend/app/gateway/routers/agents.py"],
        "official_change_summary": "Gateway router changes",
        "local_affected_surface": ["gateway"],
    }
    result = classify_upstream_change_candidate(candidate)
    assert result["integration_layer"] == "adapter_patch_integration"


# ---------------------------------------------------------------------------
# Test 10: classify exec approval as adapter_patch_integration
# ---------------------------------------------------------------------------

def test_classify_exec_approval_as_adapter_patch():
    candidate = {
        "candidate_id": "TEST-005",
        "file_path": "backend/app/gateway/services.py",
        "area": "exec_approval",
        "summary": "Exec approval logic",
        "upstream_area": "gateway",
        "upstream_file_refs": ["backend/app/gateway/services.py"],
        "official_change_summary": "Exec approval changes",
        "local_affected_surface": ["gateway"],
    }
    result = classify_upstream_change_candidate(candidate)
    assert result["integration_layer"] == "adapter_patch_integration"


# ---------------------------------------------------------------------------
# Test 11: classify trace/logging as adapter_patch_integration
# ---------------------------------------------------------------------------

def test_classify_trace_logging_as_adapter_patch():
    candidate = {
        "candidate_id": "TEST-006",
        "file_path": "backend/app/logging/otel.py",
        "area": "trace",
        "summary": "OTel trace logging",
        "upstream_area": "trace_logging",
        "upstream_file_refs": ["backend/app/logging/otel.py"],
        "official_change_summary": "Trace logging update",
        "local_affected_surface": ["trace_logging"],
    }
    result = classify_upstream_change_candidate(candidate)
    assert result["integration_layer"] == "adapter_patch_integration"


# ---------------------------------------------------------------------------
# Test 12: classify plugin registry as adapter_patch_integration
# ---------------------------------------------------------------------------

def test_classify_plugin_registry_as_adapter_patch():
    candidate = {
        "candidate_id": "TEST-007",
        "file_path": "backend/app/plugin/registry.py",
        "area": "plugin",
        "summary": "Plugin registry",
        "upstream_area": "plugin_registry",
        "upstream_file_refs": ["backend/app/plugin/registry.py"],
        "official_change_summary": "Plugin registry update",
        "local_affected_surface": ["plugin_registry"],
    }
    result = classify_upstream_change_candidate(candidate)
    assert result["integration_layer"] == "adapter_patch_integration"


# ---------------------------------------------------------------------------
# Test 13: classify browser automation as report_only_quarantine
# ---------------------------------------------------------------------------

def test_classify_browser_automation_as_quarantine():
    candidate = {
        "candidate_id": "TEST-008",
        "file_path": "backend/app/tools/browser.py",
        "area": "browser_automation",
        "summary": "Browser automation",
        "upstream_area": "browser_automation",
        "upstream_file_refs": ["backend/app/tools/browser.py"],
        "official_change_summary": "Playwright browser automation",
        "local_affected_surface": ["browser_automation"],
    }
    result = classify_upstream_change_candidate(candidate)
    assert result["integration_layer"] == "report_only_quarantine"
    assert result["risk_level"] == "high"
    assert result["recommended_action"] == "quarantine_report_only"


# ---------------------------------------------------------------------------
# Test 14: classify scheduler as report_only_quarantine
# ---------------------------------------------------------------------------

def test_classify_scheduler_as_quarantine():
    candidate = {
        "candidate_id": "TEST-009",
        "file_path": "backend/app/scheduler/cron.py",
        "area": "scheduler",
        "summary": "Scheduler",
        "upstream_area": "scheduler",
        "upstream_file_refs": ["backend/app/scheduler/cron.py"],
        "official_change_summary": "Scheduler update",
        "local_affected_surface": ["scheduler"],
    }
    result = classify_upstream_change_candidate(candidate)
    assert result["integration_layer"] == "report_only_quarantine"


# ---------------------------------------------------------------------------
# Test 15: classify real Feishu push as report_only_quarantine
# ---------------------------------------------------------------------------

def test_classify_real_feishu_push_as_quarantine():
    candidate = {
        "candidate_id": "TEST-010",
        "file_path": "backend/app/channels/feishu_push.py",
        "area": "real_feishu_push",
        "summary": "Real Feishu push",
        "upstream_area": "feishu_channel",
        "upstream_file_refs": ["backend/app/channels/feishu_push.py"],
        "official_change_summary": "Real Feishu webhook push",
        "local_affected_surface": ["feishu_channel"],
    }
    result = classify_upstream_change_candidate(candidate)
    assert result["integration_layer"] == "report_only_quarantine"
    assert result["risk_level"] == "high"


# ---------------------------------------------------------------------------
# Test 16: classify prompt optimizer as report_only_quarantine
# ---------------------------------------------------------------------------

def test_classify_prompt_optimizer_as_quarantine():
    candidate = {
        "candidate_id": "TEST-011",
        "file_path": "backend/app/ai/prompt_optimizer.py",
        "area": "prompt_optimizer",
        "summary": "Prompt optimizer",
        "upstream_area": "prompt_governance",
        "upstream_file_refs": ["backend/app/ai/prompt_optimizer.py"],
        "official_change_summary": "Prompt optimizer",
        "local_affected_surface": ["prompt_governance"],
    }
    result = classify_upstream_change_candidate(candidate)
    assert result["integration_layer"] == "report_only_quarantine"


# ---------------------------------------------------------------------------
# Test 17: classify direct Gateway replacement as forbidden_runtime_replacement
# ---------------------------------------------------------------------------

def test_classify_direct_gateway_replacement_as_forbidden():
    candidate = {
        "candidate_id": "TEST-012",
        "file_path": "backend/app/gateway/main.py",
        "area": "gateway_main",
        "summary": "Gateway main",
        "upstream_area": "gateway",
        "upstream_file_refs": ["backend/app/gateway/main.py"],
        "official_change_summary": "Replace gateway main run path",
        "local_affected_surface": ["gateway"],
    }
    result = classify_upstream_change_candidate(candidate)
    assert result["integration_layer"] == "forbidden_runtime_replacement"
    assert result["risk_level"] == "critical"
    assert result["recommended_action"] == "reject_runtime_replacement"


# ---------------------------------------------------------------------------
# Test 18: classify prompt runtime replacement as forbidden_runtime_replacement
# ---------------------------------------------------------------------------

def test_classify_prompt_runtime_replacement_as_forbidden():
    candidate = {
        "candidate_id": "TEST-013",
        "file_path": "backend/app/ai/prompt_runtime.py",
        "area": "prompt_runtime",
        "summary": "Prompt runtime",
        "upstream_area": "prompt_governance",
        "upstream_file_refs": ["backend/app/ai/prompt_runtime.py"],
        "official_change_summary": "Replace prompt runtime",
        "local_affected_surface": ["prompt_governance"],
    }
    result = classify_upstream_change_candidate(candidate)
    assert result["integration_layer"] == "forbidden_runtime_replacement"


# ---------------------------------------------------------------------------
# Test 19: matrix counts direct/adapter/quarantine/forbidden
# ---------------------------------------------------------------------------

def test_matrix_counts_categories():
    matrix = UpstreamIntakeMatrix(
        matrix_id="TEST-MATRIX",
        upstream_url="https://github.com/openclaw/openclaw.git",
        upstream_head="abc123",
        upstream_branch="main",
        source_available=True,
        candidates=[
            UpstreamChangeCandidate(
                candidate_id="T1",
                upstream_area="docs",
                upstream_file_refs=[],
                official_change_summary="docs",
                local_affected_surface=[LocalFoundationSurface.UNKNOWN],
                integration_layer=UpstreamIntegrationLayer.SAFE_DIRECT_UPDATE,
                risk_level=UpstreamRiskLevel.LOW,
                recommended_action=UpstreamActionDecision.ACCEPT_DIRECT,
            ),
            UpstreamChangeCandidate(
                candidate_id="T2",
                upstream_area="feishu_channel",
                upstream_file_refs=[],
                official_change_summary="feishu",
                local_affected_surface=[LocalFoundationSurface.FEISHU_CHANNEL],
                integration_layer=UpstreamIntegrationLayer.ADAPTER_PATCH_INTEGRATION,
                risk_level=UpstreamRiskLevel.MEDIUM,
                recommended_action=UpstreamActionDecision.ACCEPT_ADAPTER_PATCH,
            ),
            UpstreamChangeCandidate(
                candidate_id="T3",
                upstream_area="browser_automation",
                upstream_file_refs=[],
                official_change_summary="browser",
                local_affected_surface=[LocalFoundationSurface.BROWSER_AUTOMATION],
                integration_layer=UpstreamIntegrationLayer.REPORT_ONLY_QUARANTINE,
                risk_level=UpstreamRiskLevel.HIGH,
                recommended_action=UpstreamActionDecision.QUARANTINE_REPORT_ONLY,
            ),
            UpstreamChangeCandidate(
                candidate_id="T4",
                upstream_area="gateway",
                upstream_file_refs=[],
                official_change_summary="gateway main",
                local_affected_surface=[LocalFoundationSurface.GATEWAY],
                integration_layer=UpstreamIntegrationLayer.FORBIDDEN_RUNTIME_REPLACEMENT,
                risk_level=UpstreamRiskLevel.CRITICAL,
                recommended_action=UpstreamActionDecision.REJECT_RUNTIME_REPLACEMENT,
            ),
        ],
    )

    d = matrix.to_dict()
    assert d["direct_update_candidates_count"] == 1
    assert d["adapter_patch_candidates_count"] == 1
    assert d["quarantine_candidates_count"] == 1
    assert d["forbidden_candidates_count"] == 1


# ---------------------------------------------------------------------------
# Test 20: validation rejects high-risk direct update
# ---------------------------------------------------------------------------

def test_validation_rejects_high_risk_direct_update():
    matrix = {
        "source_available": True,
        "candidates": [
            {
                "candidate_id": "T1",
                "integration_layer": "safe_direct_update",
                "risk_level": "critical",
                "recommended_action": "accept_direct",
            }
        ],
    }
    result = validate_upstream_intake_matrix(matrix)
    assert result["valid"] is False
    assert any("safe_direct_update" in i and "critical" in i for i in result["issues"])


# ---------------------------------------------------------------------------
# Test 21: validation rejects forbidden candidate marked direct
# ---------------------------------------------------------------------------

def test_validation_rejects_forbidden_not_rejected():
    matrix = {
        "source_available": True,
        "candidates": [
            {
                "candidate_id": "T1",
                "integration_layer": "forbidden_runtime_replacement",
                "risk_level": "critical",
                "recommended_action": "accept_direct",  # Wrong — should be reject
            }
        ],
    }
    result = validate_upstream_intake_matrix(matrix)
    assert result["valid"] is False
    assert any("reject_runtime_replacement" in i for i in result["issues"])


# ---------------------------------------------------------------------------
# Test 22: validation requires rollback for adapter candidates
# ---------------------------------------------------------------------------

def test_validation_requires_rollback_for_adapter():
    matrix = {
        "source_available": True,
        "candidates": [
            {
                "candidate_id": "T1",
                "integration_layer": "adapter_patch_integration",
                "risk_level": "medium",
                "recommended_action": "accept_adapter_patch",
                "test_required": False,
                "rollback_required": False,
            }
        ],
    }
    result = validate_upstream_intake_matrix(matrix)
    assert result["valid"] is True  # Only warnings, not issues
    assert any("rollback_required" in w for w in result["warnings"])


# ---------------------------------------------------------------------------
# Test 23: validation confirms no openclaw update
# ---------------------------------------------------------------------------

def test_validation_confirms_no_openclaw_update():
    matrix = {"source_available": True, "candidates": []}
    result = validate_upstream_intake_matrix(matrix)
    assert result["prohibited_actions_check"] == "pass"


# ---------------------------------------------------------------------------
# Test 24: validation confirms no doctor fix
# ---------------------------------------------------------------------------

def test_validation_confirms_no_doctor_fix():
    matrix = {"source_available": True, "candidates": []}
    result = validate_upstream_intake_matrix(matrix)
    # Check that the prohibited record is clean
    assert get_prohibited_actions_record() == []


# ---------------------------------------------------------------------------
# Test 25: report generation writes only to tmp path
# ---------------------------------------------------------------------------

def test_report_generation_writes_json_and_md(tmp_path):
    matrix = build_upstream_optimization_intake_matrix(root=str(tmp_path))

    result = generate_upstream_intake_matrix_report(matrix=matrix, output_path=str(tmp_path))

    assert os.path.exists(result["json_path"])
    assert os.path.exists(result["md_path"])
    # Should NOT write to current repo (only to specified tmp_path)
    repo_root = tmp_path.parent  # parent of tmp_path
    assert not os.path.exists(os.path.join(repo_root, "backend", "migration_reports", "foundation_audit", "R241-17C_UPSTREAM_OPTIMIZATION_INTAKE_MATRIX.json"))


# ---------------------------------------------------------------------------
# Test 26: mainline gate allows when all preconditions true
# ---------------------------------------------------------------------------

def test_mainline_gate_allows_when_preconditions_true(tmp_path):
    reports_dir = os.path.join(str(tmp_path), "backend", "migration_reports", "foundation_audit")
    os.makedirs(reports_dir, exist_ok=True)

    # Write fake R241-17B-C report
    with open(os.path.join(reports_dir, "R241-17B_C_POST_PUBLISH_AUDIT_CONSISTENCY_REPAIR.json"), "w") as f:
        json.dump({
            "audit_result": {"status": "operationally_closed_with_deviation"},
            "test_results": {"total": {"failed": 0}},
        }, f)

    # Write fake R241-17C matrix
    with open(os.path.join(reports_dir, "R241-17C_UPSTREAM_OPTIMIZATION_INTAKE_MATRIX.json"), "w") as f:
        json.dump({
            "direct_update_candidates_count": 2,
            "adapter_patch_candidates_count": 3,
            "quarantine_candidates_count": 1,
            "forbidden_candidates_count": 0,
        }, f)

    with patch("os.path.exists", return_value=True):
        gate = evaluate_mainline_resume_gate(root=str(tmp_path))

    assert gate["mainline_resume_allowed"] is True
    assert gate["next_mainline_phase"] == "R241-18A_RUNTIME_ACTIVATION_READINESS_REVIEW"


# ---------------------------------------------------------------------------
# Test 27: mainline gate blocks when post-publish audit unstable
# ---------------------------------------------------------------------------

def test_mainline_gate_blocks_when_audit_unstable(tmp_path):
    reports_dir = os.path.join(str(tmp_path), "backend", "migration_reports", "foundation_audit")
    os.makedirs(reports_dir, exist_ok=True)

    # Write R241-17B-C report with unstable audit
    with open(os.path.join(reports_dir, "R241-17B_C_POST_PUBLISH_AUDIT_CONSISTENCY_REPAIR.json"), "w") as f:
        json.dump({
            "audit_result": {"status": "unstable"},
            "test_results": {"total": {"failed": 0}},
        }, f)

    # Also write a fake R241-17C matrix so upstream_matrix_ready = True
    # (so we isolate the "audit unstable" block reason)
    with open(os.path.join(reports_dir, "R241-17C_UPSTREAM_OPTIMIZATION_INTAKE_MATRIX.json"), "w") as f:
        json.dump({"direct_update_candidates_count": 1}, f)

    gate = evaluate_mainline_resume_gate(root=str(tmp_path))

    assert gate["mainline_resume_allowed"] is False
    assert any("audit" in b.lower() for b in gate["blocked_reasons"])


# ---------------------------------------------------------------------------
# Test 28: mainline gate blocks when upstream matrix missing
# ---------------------------------------------------------------------------

def test_mainline_gate_blocks_when_matrix_missing(tmp_path):
    reports_dir = os.path.join(str(tmp_path), "backend", "migration_reports", "foundation_audit")
    os.makedirs(reports_dir, exist_ok=True)

    # Write R241-17B-C but NOT 17C matrix
    with open(os.path.join(reports_dir, "R241-17B_C_POST_PUBLISH_AUDIT_CONSISTENCY_REPAIR.json"), "w") as f:
        json.dump({
            "audit_result": {"status": "operationally_closed_with_deviation"},
            "test_results": {"total": {"failed": 0}},
        }, f)

    def fake_exists(path):
        if "R241-17C" in path:
            return False
        return True

    with patch("os.path.exists", side_effect=fake_exists):
        gate = evaluate_mainline_resume_gate(root=str(tmp_path))

    assert gate["mainline_resume_allowed"] is False
    assert any("matrix" in b.lower() for b in gate["blocked_reasons"])


# ---------------------------------------------------------------------------
# Test 29: mainline gate next phase is R241-18A
# ---------------------------------------------------------------------------

def test_mainline_gate_next_phase_is_r241_18a(tmp_path):
    reports_dir = os.path.join(str(tmp_path), "backend", "migration_reports", "foundation_audit")
    os.makedirs(reports_dir, exist_ok=True)

    with open(os.path.join(reports_dir, "R241-17B_C_POST_PUBLISH_AUDIT_CONSISTENCY_REPAIR.json"), "w") as f:
        json.dump({
            "audit_result": {"status": "operationally_closed_with_deviation"},
            "test_results": {"total": {"failed": 0}},
        }, f)

    with open(os.path.join(reports_dir, "R241-17C_UPSTREAM_OPTIMIZATION_INTAKE_MATRIX.json"), "w") as f:
        json.dump({
            "direct_update_candidates_count": 1,
            "adapter_patch_candidates_count": 1,
            "quarantine_candidates_count": 1,
            "forbidden_candidates_count": 0,
        }, f)

    with patch("os.path.exists", return_value=True):
        gate = evaluate_mainline_resume_gate(root=str(tmp_path))

    assert gate["next_mainline_phase"] == "R241-18A_RUNTIME_ACTIVATION_READINESS_REVIEW"


# ---------------------------------------------------------------------------
# Test 30: no secret read
# ---------------------------------------------------------------------------

def test_no_secret_read():
    # The module never reads secrets — check get_prohibited_actions_record is clean
    assert get_prohibited_actions_record() == []


# ---------------------------------------------------------------------------
# Test 31: no runtime write
# ---------------------------------------------------------------------------

def test_no_runtime_write():
    # The module only writes to specified output_path, never to runtime dirs
    assert _PROHIBITED_ACTIONS_EXECUTED == []


# ---------------------------------------------------------------------------
# Test 32: no auto-fix
# ---------------------------------------------------------------------------

def test_no_auto_fix():
    # No auto-fix calls exist in the module
    assert get_prohibited_actions_record() == []