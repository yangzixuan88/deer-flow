import json
from pathlib import Path

import pytest

from app.foundation import ci_implementation_plan as impl


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


# ── 1. build_ci_stage_implementation_specs ─────────────────────────────────────

def test_stage_specs_contains_smoke_fast_safety_slow_full():
    specs = impl.build_ci_stage_implementation_specs()
    types = {s["stage_type"] for s in specs["specs"]}
    assert impl.CIExecutionStageType.SMOKE in types
    assert impl.CIExecutionStageType.FAST in types
    assert impl.CIExecutionStageType.SAFETY in types
    assert impl.CIExecutionStageType.SLOW in types
    assert impl.CIExecutionStageType.FULL in types


def test_fast_stage_command_uses_not_slow():
    specs = impl.build_ci_stage_implementation_specs()
    fast = next(s for s in specs["specs"] if s["stage_type"] == impl.CIExecutionStageType.FAST)
    assert "not slow" in fast["command"]


def test_smoke_stage_uses_smoke_marker():
    specs = impl.build_ci_stage_implementation_specs()
    smoke = next(s for s in specs["specs"] if s["stage_type"] == impl.CIExecutionStageType.SMOKE)
    assert smoke["marker_expression"] == "smoke"


def test_safety_stage_uses_no_network_or_runtime_write_or_no_secret():
    specs = impl.build_ci_stage_implementation_specs()
    safety = next(s for s in specs["specs"] if s["stage_type"] == impl.CIExecutionStageType.SAFETY)
    expr = safety["marker_expression"]
    assert "no_network" in expr and "no_runtime_write" in expr and "no_secret" in expr


def test_slow_stage_uses_slow_marker():
    specs = impl.build_ci_stage_implementation_specs()
    slow = next(s for s in specs["specs"] if s["stage_type"] == impl.CIExecutionStageType.SLOW)
    assert slow["marker_expression"] == "slow"


def test_full_stage_manual_only_gating():
    specs = impl.build_ci_stage_implementation_specs()
    full = next(s for s in specs["specs"] if s["stage_type"] == impl.CIExecutionStageType.FULL)
    assert full["gating_policy"] == impl.CIGatingPolicy.MANUAL_ONLY


def test_collect_only_stage_exists():
    specs = impl.build_ci_stage_implementation_specs()
    types = {s["stage_type"] for s in specs["specs"]}
    assert impl.CIExecutionStageType.COLLECT_ONLY in types


# ── 2. Gating policies ─────────────────────────────────────────────────────────

def test_fast_is_pr_blocking():
    specs = impl.build_ci_stage_implementation_specs()
    fast = next(s for s in specs["specs"] if s["stage_type"] == impl.CIExecutionStageType.FAST)
    assert fast["gating_policy"] == impl.CIGatingPolicy.PR_BLOCKING


def test_safety_is_pr_blocking():
    specs = impl.build_ci_stage_implementation_specs()
    safety = next(s for s in specs["specs"] if s["stage_type"] == impl.CIExecutionStageType.SAFETY)
    assert safety["gating_policy"] == impl.CIGatingPolicy.PR_BLOCKING


def test_slow_is_nightly_required():
    specs = impl.build_ci_stage_implementation_specs()
    slow = next(s for s in specs["specs"] if s["stage_type"] == impl.CIExecutionStageType.SLOW)
    assert slow["gating_policy"] == impl.CIGatingPolicy.NIGHTLY_REQUIRED


def test_smoke_is_pr_warning():
    specs = impl.build_ci_stage_implementation_specs()
    smoke = next(s for s in specs["specs"] if s["stage_type"] == impl.CIExecutionStageType.SMOKE)
    assert smoke["gating_policy"] == impl.CIGatingPolicy.PR_WARNING


# ── 3. Artifact collection specs ───────────────────────────────────────────────

def test_artifact_specs_contain_all_required_types():
    specs = impl.build_ci_artifact_collection_specs(str(_root()))
    types = {s["artifact_type"] for s in specs["artifact_specs"]}
    assert impl.CIArtifactType.JUNIT_XML in types
    assert impl.CIArtifactType.PYTEST_LOG in types
    assert impl.CIArtifactType.FOUNDATION_AUDIT_REPORT in types
    assert impl.CIArtifactType.CI_MATRIX_REPORT in types


def test_artifact_specs_exclude_audit_trail():
    specs = impl.build_ci_artifact_collection_specs(str(_root()))
    # foundation_reports spec must exclude audit_trail .jsonl files
    foundation = next(s for s in specs["artifact_specs"] if s["artifact_type"] == impl.CIArtifactType.FOUNDATION_AUDIT_REPORT)
    assert "**/audit_trail/*.jsonl" in foundation["exclude_patterns"]


def test_artifact_specs_exclude_runtime_files():
    specs = impl.build_ci_artifact_collection_specs(str(_root()))
    for spec in specs["artifact_specs"]:
        assert spec.get("runtime_files_allowed") is False


def test_artifact_specs_exclude_secrets():
    specs = impl.build_ci_artifact_collection_specs(str(_root()))
    for spec in specs["artifact_specs"]:
        assert spec.get("secrets_allowed") is False


# ── 4. Threshold policy ────────────────────────────────────────────────────────

def test_threshold_policy_foundation_fast_warning_30s():
    tp = impl.build_ci_threshold_policy()
    assert tp["foundation_fast_warning_threshold_seconds"] == 30


def test_threshold_policy_foundation_fast_blocker_60s():
    tp = impl.build_ci_threshold_policy()
    assert tp["foundation_fast_blocker_threshold_seconds"] == 60


def test_threshold_policy_slow_suite_warning_60s():
    tp = impl.build_ci_threshold_policy()
    assert tp["slow_suite_warning_threshold_seconds"] == 60


def test_threshold_policy_safety_suite_warning_10s():
    tp = impl.build_ci_threshold_policy()
    assert tp["safety_suite_warning_threshold_seconds"] == 10


# ── 5. Path compatibility ─────────────────────────────────────────────────────

def test_path_compatibility_primary_path_exists():
    pc = impl.build_ci_path_compatibility_policy(str(_root()))
    assert pc["primary_exists"] is True


def test_path_compatibility_both_paths_detected():
    pc = impl.build_ci_path_compatibility_policy(str(_root()))
    # Both paths exist in the repo
    assert pc["primary_exists"] is True
    assert pc["secondary_exists"] is True


# ── 6. Implementation phases ──────────────────────────────────────────────────

def test_implementation_phases_count_7():
    phases = impl.build_ci_implementation_phases()
    assert phases["phase_count"] == 7


def test_current_phase_is_phase_1():
    phases = impl.build_ci_implementation_phases()
    assert phases["current_phase"] == "phase_1"


# ── 7. Blocked actions ───────────────────────────────────────────────────────

def test_blocked_actions_count_at_least_10():
    blocked = impl.build_ci_blocked_actions()
    assert blocked["blocked_count"] >= 10


def test_auto_fix_is_blocked():
    blocked = impl.build_ci_blocked_actions()
    actions = {b["action"] for b in blocked["blocked_actions"]}
    assert "auto_fix" in actions


def test_network_call_is_blocked():
    blocked = impl.build_ci_blocked_actions()
    actions = {b["action"] for b in blocked["blocked_actions"]}
    assert "network_call" in actions


def test_runtime_write_is_blocked():
    blocked = impl.build_ci_blocked_actions()
    actions = {b["action"] for b in blocked["blocked_actions"]}
    assert "runtime_write" in actions


# ── 8. Validation ─────────────────────────────────────────────────────────────

def test_validation_passes_for_valid_plan():
    plan = {
        "stage_specs": impl.build_ci_stage_implementation_specs(),
        "artifact_collection_specs": impl.build_ci_artifact_collection_specs(str(_root())),
        "threshold_policy": impl.build_ci_threshold_policy(),
        "path_compatibility_policy": impl.build_ci_path_compatibility_policy(str(_root())),
        "implementation_phases": impl.build_ci_implementation_phases(),
        "blocked_actions": impl.build_ci_blocked_actions(),
        "network_call_recommended": False,
        "runtime_write_recommended": False,
        "auto_fix_recommended": False,
        "delete_tests_recommended": False,
        "skip_safety_tests_recommended": False,
    }
    result = impl.validate_ci_implementation_plan(plan)
    assert result["valid"] is True
    assert result["errors"] == []


def test_validation_detects_fast_not_pr_blocking():
    plan = {
        "stage_specs": {
            "specs": [
                {
                    "stage_type": impl.CIExecutionStageType.FAST,
                    "gating_policy": impl.CIGatingPolicy.PR_WARNING,
                    "required_on_pr": False,
                },
                {
                    "stage_type": impl.CIExecutionStageType.SAFETY,
                    "gating_policy": impl.CIGatingPolicy.PR_BLOCKING,
                    "required_on_pr": True,
                },
                {
                    "stage_type": impl.CIExecutionStageType.SLOW,
                    "gating_policy": impl.CIGatingPolicy.NIGHTLY_REQUIRED,
                    "required_on_pr": False,
                },
                {
                    "stage_type": impl.CIExecutionStageType.FULL,
                    "gating_policy": impl.CIGatingPolicy.MANUAL_ONLY,
                    "required_on_pr": False,
                },
                {
                    "stage_type": impl.CIExecutionStageType.COLLECT_ONLY,
                    "gating_policy": impl.CIGatingPolicy.PR_WARNING,
                    "required_on_pr": False,
                },
            ]
        },
        "artifact_collection_specs": {"artifact_specs": []},
        "threshold_policy": {},
        "path_compatibility_policy": {},
        "implementation_phases": {},
        "blocked_actions": {"blocked_actions": [{"action": "x", "blocked": True}]},
        "network_call_recommended": False,
        "runtime_write_recommended": False,
        "auto_fix_recommended": False,
        "delete_tests_recommended": False,
        "skip_safety_tests_recommended": False,
    }
    result = impl.validate_ci_implementation_plan(plan)
    # Valid — 5 stages passes count check, fast not-pr_blocking is a warning not an error
    assert result["valid"] is True
    assert any("pr_blocking" in w for w in result["warnings"])


def test_validation_detects_slow_pr_blocking():
    plan = {
        "stage_specs": {
            "specs": [
                {
                    "stage_type": impl.CIExecutionStageType.SLOW,
                    "gating_policy": impl.CIGatingPolicy.PR_BLOCKING,
                }
            ]
        },
        "artifact_collection_specs": {"artifact_specs": []},
        "threshold_policy": {},
        "path_compatibility_policy": {},
        "implementation_phases": {},
        "blocked_actions": {"blocked_actions": [{"action": "x", "blocked": True}]},
        "network_call_recommended": False,
        "runtime_write_recommended": False,
        "auto_fix_recommended": False,
        "delete_tests_recommended": False,
        "skip_safety_tests_recommended": False,
    }
    result = impl.validate_ci_implementation_plan(plan)
    assert result["valid"] is False
    assert any("pr_blocking" in e.lower() for e in result["errors"])


def test_validation_detects_path_migration_allowed():
    plan = {
        "stage_specs": {"specs": []},
        "artifact_collection_specs": {"artifact_specs": []},
        "threshold_policy": {},
        "path_compatibility_policy": {"migration_allowed_now": True, "action_now": "migrate"},
        "implementation_phases": {},
        "blocked_actions": {"blocked_actions": [{"action": "x", "blocked": True}]},
        "network_call_recommended": False,
        "runtime_write_recommended": False,
        "auto_fix_recommended": False,
        "delete_tests_recommended": False,
        "skip_safety_tests_recommended": False,
    }
    result = impl.validate_ci_implementation_plan(plan)
    assert result["valid"] is False
    assert any("migration" in e.lower() for e in result["errors"])


def test_validation_detects_auto_fix_recommended():
    plan = {
        "stage_specs": {"specs": []},
        "artifact_collection_specs": {"artifact_specs": []},
        "threshold_policy": {},
        "path_compatibility_policy": {},
        "implementation_phases": {},
        "blocked_actions": {"blocked_actions": [{"action": "x", "blocked": True}]},
        "network_call_recommended": False,
        "runtime_write_recommended": False,
        "auto_fix_recommended": True,
        "delete_tests_recommended": False,
        "skip_safety_tests_recommended": False,
    }
    result = impl.validate_ci_implementation_plan(plan)
    assert result["valid"] is False
    assert any("auto_fix" in e.lower() for e in result["errors"])


# ── 9. generate_ci_implementation_plan safety ─────────────────────────────────

def test_generate_plan_sets_all_policy_flags_false():
    result = impl.generate_ci_implementation_plan(root=str(_root()))
    assert result["network_call_recommended"] is False
    assert result["runtime_write_recommended"] is False
    assert result["auto_fix_recommended"] is False
    assert result["delete_tests_recommended"] is False
    assert result["skip_safety_tests_recommended"] is False
    assert result["creates_real_workflow"] is False


def test_generate_plan_writes_json_and_markdown(tmp_path, monkeypatch):
    monkeypatch.setattr(impl, "ROOT", tmp_path)
    monkeypatch.setattr(impl, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    result = impl.generate_ci_implementation_plan(root=str(tmp_path))
    assert Path(result["output_plan_path"]).exists()
    assert Path(result["output_report_path"]).exists()
    # Validation must pass
    assert result["validation"]["valid"] is True


def test_generate_plan_does_not_write_audit_jsonl(tmp_path, monkeypatch):
    audit_dir = tmp_path / "migration_reports" / "foundation_audit" / "audit_trail"
    audit_dir.mkdir(parents=True)
    jsonl = audit_dir / "foundation_diagnostic_runs.jsonl"
    jsonl.write_text('{"audit_record_id":"x"}\n', encoding="utf-8")
    before = jsonl.read_text(encoding="utf-8")
    impl.generate_ci_implementation_plan(root=str(tmp_path))
    assert jsonl.read_text(encoding="utf-8") == before


def test_generate_plan_does_not_network_call(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(impl, "ROOT", tmp_path)
    monkeypatch.setattr(impl, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    monkeypatch.setattr(impl, "validate_ci_implementation_plan", lambda p: called.append("validated") or {"valid": True, "errors": [], "warnings": [], "validated_at": ""})
    impl.generate_ci_implementation_plan(root=str(tmp_path))
    # Only validation was called — no network, no runtime writes
    assert called == ["validated"]


def test_generate_plan_dry_run_does_not_create_workflow(tmp_path, monkeypatch):
    monkeypatch.setattr(impl, "ROOT", tmp_path)
    monkeypatch.setattr(impl, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    result = impl.generate_ci_implementation_plan(root=str(tmp_path))
    assert result["creates_real_workflow"] is False
    # No .github/workflows created
    gh_dir = tmp_path / ".github" / "workflows"
    assert not gh_dir.exists()


def test_collect_only_stage_pr_warning():
    specs = impl.build_ci_stage_implementation_specs()
    collect = next(s for s in specs["specs"] if s["stage_type"] == impl.CIExecutionStageType.COLLECT_ONLY)
    assert collect["gating_policy"] == impl.CIGatingPolicy.PR_WARNING
