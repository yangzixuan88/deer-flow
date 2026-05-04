"""Tests for R241-16S ci_publish_patch_bundle_generation module."""

from pathlib import Path
import json
import pytest

from app.foundation import ci_publish_patch_bundle_generation as patch_bundle


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


# ── Test load_recovery_gate_for_patch_bundle ────────────────────────────────

def test_load_gate_reads_r241_16r_result():
    result = patch_bundle.load_recovery_gate_for_patch_bundle(str(_root()))
    assert result["loaded"] is True
    assert result["passed"] is True


def test_load_gate_rejects_missing_file(tmp_path, monkeypatch):
    import app.foundation.ci_publish_patch_bundle_generation as pbg
    monkeypatch.setattr(pbg, "R241_16R_GATE_PATH", tmp_path / "nonexistent" / "R241-16R.json")
    result = pbg.load_recovery_gate_for_patch_bundle()
    assert result["loaded"] is False
    assert result["passed"] is False


def test_load_gate_checks_recovery_action_flag():
    result = patch_bundle.load_recovery_gate_for_patch_bundle(str(_root()))
    assert result["gate_recovery_action_allowed_now"] is False


def test_load_gate_reads_next_phase_recommendation():
    result = patch_bundle.load_recovery_gate_for_patch_bundle(str(_root()))
    assert result["gate_allowed_next_phase"] == "R241-16S_patch_bundle_generation"


# ── Test run_patch_bundle_prechecks ─────────────────────────────────────────

def test_prechecks_run_git_available_check():
    result = patch_bundle.run_patch_bundle_prechecks(str(_root()))
    checks = {c["check_id"] for c in result["checks"]}
    assert "git_available" in checks


def test_prechecks_run_local_commit_exists_check():
    result = patch_bundle.run_patch_bundle_prechecks(str(_root()))
    checks = {c["check_id"] for c in result["checks"]}
    assert "local_commit_exists" in checks


def test_prechecks_run_head_matches_commit_check():
    result = patch_bundle.run_patch_bundle_prechecks(str(_root()))
    checks = {c["check_id"] for c in result["checks"]}
    assert "head_matches_commit" in checks


def test_prechecks_run_staged_area_empty_check():
    result = patch_bundle.run_patch_bundle_prechecks(str(_root()))
    checks = {c["check_id"] for c in result["checks"]}
    assert "staged_area_empty" in checks


def test_prechecks_run_workflow_content_safe_check():
    result = patch_bundle.run_patch_bundle_prechecks(str(_root()))
    checks = {c["check_id"] for c in result["checks"]}
    assert "workflow_content_safe" in checks


def test_prechecks_run_output_directory_exists_check():
    result = patch_bundle.run_patch_bundle_prechecks(str(_root()))
    checks = {c["check_id"] for c in result["checks"]}
    assert "output_directory_exists" in checks


def test_prechecks_all_passed_when_gate_passes():
    result = patch_bundle.run_patch_bundle_prechecks(str(_root()))
    assert result["all_passed"] is True


def test_prechecks_gate_loaded_and_passed():
    result = patch_bundle.run_patch_bundle_prechecks(str(_root()))
    assert result["gate_loaded"] is True
    assert result["gate_passed"] is True


def test_prechecks_gate_failed_returns_early(tmp_path, monkeypatch):
    import app.foundation.ci_publish_patch_bundle_generation as pbg
    # Monkeypatch R241_16R_GATE_PATH to a nonexistent file
    nonexistent_gate = str(tmp_path / "nonexistent_R241-16R.json")
    monkeypatch.setattr(pbg, "R241_16R_GATE_PATH", nonexistent_gate)
    # Use tmp_path as root so load_recovery_gate_for_patch_bundle uses the module constant
    # (when root is provided, load_recovery_gate_for_patch_bundle builds gate_path from root)
    result = pbg.run_patch_bundle_prechecks(str(tmp_path))
    assert result["gate_passed"] is False
    assert result["gate_loaded"] is False


def test_prechecks_includes_all_gate_check_types():
    result = patch_bundle.run_patch_bundle_prechecks(str(_root()))
    check_types = {c.get("check_type") for c in result["checks"]}
    assert "gate_status" in check_types
    assert "gate_decision" in check_types


# ── Test capture_patch_bundle_baseline ──────────────────────────────────────

def test_capture_baseline_returns_head_hash():
    result = patch_bundle.capture_patch_bundle_baseline(str(_root()))
    assert "head_hash" in result
    assert result["head_hash"] != ""


def test_capture_baseline_returns_branch():
    result = patch_bundle.capture_patch_bundle_baseline(str(_root()))
    assert "branch" in result


def test_capture_baseline_returns_staged_files():
    result = patch_bundle.capture_patch_bundle_baseline(str(_root()))
    assert "staged_files" in result


def test_capture_baseline_reports_audit_jsonl_line_count():
    result = patch_bundle.capture_patch_bundle_baseline(str(_root()))
    assert "audit_jsonl_line_count" in result


# ── Test generate_patch_artifact ─────────────────────────────────────────────

def test_generate_patch_artifact_runs_git_format_patch():
    result = patch_bundle.generate_patch_artifact(str(_root()), patch_bundle.SOURCE_COMMIT_HASH)
    assert result["artifact_type"] == "patch"
    assert result["command_executed"] is True
    assert result["exit_code"] == 0


def test_generate_patch_artifact_patch_exists():
    result = patch_bundle.generate_patch_artifact(str(_root()), patch_bundle.SOURCE_COMMIT_HASH)
    assert result["patch_exists"] is True


def test_generate_patch_artifact_patch_changed_files():
    result = patch_bundle.generate_patch_artifact(str(_root()), patch_bundle.SOURCE_COMMIT_HASH)
    assert "patch_changed_files" in result


def test_generate_patch_artifact_contains_only_target_workflow():
    result = patch_bundle.generate_patch_artifact(str(_root()), patch_bundle.SOURCE_COMMIT_HASH)
    assert result["contains_only_target_workflow"] is True


# ── Test generate_bundle_artifact ───────────────────────────────────────────

def test_generate_bundle_artifact_runs_git_bundle_create():
    result = patch_bundle.generate_bundle_artifact(str(_root()), patch_bundle.SOURCE_COMMIT_HASH)
    assert result["artifact_type"] == "bundle"
    assert result["command_executed"] is True
    assert result["exit_code"] == 0


def test_generate_bundle_artifact_bundle_exists():
    result = patch_bundle.generate_bundle_artifact(str(_root()), patch_bundle.SOURCE_COMMIT_HASH)
    assert result["bundle_exists"] is True


# ── Test inspect_patch_artifact ─────────────────────────────────────────────

def test_inspect_patch_artifact_checks_scope():
    patch_path = patch_bundle.REPORT_DIR / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch"
    if patch_path.exists():
        result = patch_bundle.inspect_patch_artifact(str(_root()), str(patch_path))
        checks = {c["check_id"] for c in result["checks"]}
        assert "patch_changed_files" in checks
        assert "no_forbidden_paths" in checks


def test_inspect_patch_artifact_reports_changed_files():
    patch_path = patch_bundle.REPORT_DIR / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch"
    if patch_path.exists():
        result = patch_bundle.inspect_patch_artifact(str(_root()), str(patch_path))
        assert "changed_files" in result


def test_inspect_patch_artifact_safe_to_share():
    patch_path = patch_bundle.REPORT_DIR / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch"
    if patch_path.exists():
        result = patch_bundle.inspect_patch_artifact(str(_root()), str(patch_path))
        assert result["safe_to_share"] is True


# ── Test inspect_bundle_artifact ─────────────────────────────────────────────

def test_inspect_bundle_artifact_runs_git_bundle_verify():
    bundle_path = patch_bundle.REPORT_DIR / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle"
    if bundle_path.exists():
        result = patch_bundle.inspect_bundle_artifact(str(_root()), str(bundle_path), patch_bundle.SOURCE_COMMIT_HASH)
        checks = {c["check_id"] for c in result["checks"]}
        assert "bundle_verify" in checks


def test_inspect_bundle_artifact_runs_git_bundle_list_heads():
    bundle_path = patch_bundle.REPORT_DIR / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle"
    if bundle_path.exists():
        result = patch_bundle.inspect_bundle_artifact(str(_root()), str(bundle_path), patch_bundle.SOURCE_COMMIT_HASH)
        checks = {c["check_id"] for c in result["checks"]}
        assert "bundle_contains_target_commit" in checks


def test_inspect_bundle_artifact_bundle_safe_to_share():
    bundle_path = patch_bundle.REPORT_DIR / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle"
    if bundle_path.exists():
        result = patch_bundle.inspect_bundle_artifact(str(_root()), str(bundle_path), patch_bundle.SOURCE_COMMIT_HASH)
        assert result["safe_to_share"] is True


# ── Test generate_patch_bundle_manifest ─────────────────────────────────────

def test_manifest_writes_json_file():
    result_so_far = {
        "patch_artifact": {"canonical_path": str(patch_bundle.REPORT_DIR / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch"), "patch_exists": True, "patch_sha256": "abc", "patch_size_bytes": 100},
        "bundle_artifact": {"bundle_path": str(patch_bundle.REPORT_DIR / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle"), "bundle_exists": True, "bundle_sha256": "def", "bundle_size_bytes": 200},
    }
    result = patch_bundle.generate_patch_bundle_manifest(str(_root()), result_so_far)
    assert result["manifest_exists"] is True
    assert Path(result["manifest_path"]).exists()


def test_manifest_contains_source_commit_info():
    result_so_far = {
        "patch_artifact": {"canonical_path": str(patch_bundle.REPORT_DIR / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch"), "patch_exists": True, "patch_sha256": "abc", "patch_size_bytes": 100},
        "bundle_artifact": {"bundle_path": str(patch_bundle.REPORT_DIR / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle"), "bundle_exists": True, "bundle_sha256": "def", "bundle_size_bytes": 200},
    }
    result = patch_bundle.generate_patch_bundle_manifest(str(_root()), result_so_far)
    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["source_commit_hash"] == patch_bundle.SOURCE_COMMIT_HASH
    assert manifest["source_changed_files"] == [".github/workflows/foundation-manual-dispatch.yml"]


# ── Test verify_no_local_mutation_after_patch_bundle ─────────────────────────

def test_mutation_guard_all_passed():
    baseline = patch_bundle.capture_patch_bundle_baseline(str(_root()))
    result = patch_bundle.verify_no_local_mutation_after_patch_bundle(str(_root()), baseline)
    assert result["all_passed"] is True


def test_mutation_guard_reports_head_unchanged():
    baseline = patch_bundle.capture_patch_bundle_baseline(str(_root()))
    result = patch_bundle.verify_no_local_mutation_after_patch_bundle(str(_root()), baseline)
    head_check = next((c for c in result["checks"] if c["check_id"] == "head_unchanged"), None)
    assert head_check is not None
    assert head_check["passed"] is True


def test_mutation_guard_reports_staged_area_still_empty():
    baseline = patch_bundle.capture_patch_bundle_baseline(str(_root()))
    result = patch_bundle.verify_no_local_mutation_after_patch_bundle(str(_root()), baseline)
    staged_check = next((c for c in result["checks"] if c["check_id"] == "staged_area_still_empty"), None)
    assert staged_check is not None
    assert staged_check["passed"] is True


# ── Test execute_patch_bundle_generation ─────────────────────────────────────

def test_execute_returns_full_result_keys():
    result = patch_bundle.execute_patch_bundle_generation(str(_root()), generate_bundle=True)
    assert "status" in result
    assert "decision" in result
    assert "patch_artifact" in result
    assert "bundle_artifact" in result
    assert "manifest_result" in result


def test_execute_patch_artifact_generated():
    result = patch_bundle.execute_patch_bundle_generation(str(_root()), generate_bundle=True)
    assert result["patch_generated"] is True


def test_execute_bundle_artifact_generated():
    result = patch_bundle.execute_patch_bundle_generation(str(_root()), generate_bundle=True)
    assert result["bundle_generated"] is True


def test_execute_manifest_result_generated():
    result = patch_bundle.execute_patch_bundle_generation(str(_root()), generate_bundle=True)
    assert result["manifest_generated"] is True


def test_execute_mutation_guard_all_passed():
    result = patch_bundle.execute_patch_bundle_generation(str(_root()), generate_bundle=True)
    assert result["local_mutation_guard"]["all_passed"] is True


def test_execute_status_is_generated():
    result = patch_bundle.execute_patch_bundle_generation(str(_root()), generate_bundle=True)
    assert result["status"] == patch_bundle.PatchBundleGenerationStatus.GENERATED.value


def test_execute_patch_only_mode():
    result = patch_bundle.execute_patch_bundle_generation(str(_root()), generate_bundle=False)
    assert result["patch_generated"] is True
    assert result["bundle_generated"] is False


# ── Test validate_patch_bundle_generation_result ─────────────────────────────

def test_validate_accepts_valid_result():
    result = patch_bundle.execute_patch_bundle_generation(str(_root()), generate_bundle=True)
    validation = patch_bundle.validate_patch_bundle_generation_result(result)
    assert validation["valid"] is True


def test_validate_rejects_result_with_forbidden_commands():
    bad_result = {
        "git_command_results": [{"argv": ["git", "push"], "exit_code": 0}],
        "local_mutation_guard": {"all_passed": True},
        "artifacts": [],
        "patch_artifact": {},
    }
    validation = patch_bundle.validate_patch_bundle_generation_result(bad_result)
    assert validation["valid"] is False


def test_validate_rejects_result_with_unsafe_patch():
    unsafe_result = {
        "git_command_results": [],
        "local_mutation_guard": {"all_passed": True},
        "artifacts": [],
        "patch_artifact": {"patch_exists": True, "contains_only_target_workflow": False},
    }
    validation = patch_bundle.validate_patch_bundle_generation_result(unsafe_result)
    assert validation["valid"] is False
    assert "patch_contains_extra_files" in validation["blocked_reasons"]


# ── Test generate_patch_bundle_generation_report ─────────────────────────────

def test_report_writes_json_output_file(tmp_path, monkeypatch):
    monkeypatch.setattr(patch_bundle, "ROOT", tmp_path)
    monkeypatch.setattr(patch_bundle, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    result = patch_bundle.execute_patch_bundle_generation(str(_root()), generate_bundle=True)
    report = patch_bundle.generate_patch_bundle_generation_report(result, str(tmp_path / "R241-16S.json"))
    assert Path(report["output_path"]).exists()


def test_report_writes_markdown_file(tmp_path, monkeypatch):
    monkeypatch.setattr(patch_bundle, "ROOT", tmp_path)
    monkeypatch.setattr(patch_bundle, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    result = patch_bundle.execute_patch_bundle_generation(str(_root()), generate_bundle=True)
    report = patch_bundle.generate_patch_bundle_generation_report(result, str(tmp_path / "R241-16S.json"))
    assert Path(report["report_path"]).exists()


def test_report_no_runtime_write(tmp_path, monkeypatch):
    monkeypatch.setattr(patch_bundle, "ROOT", tmp_path)
    monkeypatch.setattr(patch_bundle, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    result = patch_bundle.execute_patch_bundle_generation(str(_root()), generate_bundle=True)
    patch_bundle.generate_patch_bundle_generation_report(result, str(tmp_path / "R241-16S.json"))
    assert not (tmp_path / "runtime").exists()


def test_report_no_audit_jsonl_write(tmp_path, monkeypatch):
    audit_dir = tmp_path / "migration_reports" / "foundation_audit" / "audit_trail"
    audit_dir.mkdir(parents=True, exist_ok=True)
    jsonl = audit_dir / "foundation_diagnostic_runs.jsonl"
    jsonl.write_text('{"audit_record_id":"x"}\n', encoding="utf-8")
    before = jsonl.read_text(encoding="utf-8")
    monkeypatch.setattr(patch_bundle, "ROOT", tmp_path)
    monkeypatch.setattr(patch_bundle, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    result = patch_bundle.execute_patch_bundle_generation(str(_root()), generate_bundle=True)
    patch_bundle.generate_patch_bundle_generation_report(result, str(tmp_path / "R241-16S.json"))
    assert jsonl.read_text(encoding="utf-8") == before


# ── Test no mutation during generation ──────────────────────────────────────

def test_no_workflow_modification_during_execution():
    workflow_path = _root() / ".github" / "workflows" / "foundation-manual-dispatch.yml"
    before_content = workflow_path.read_text(encoding="utf-8") if workflow_path.exists() else ""
    patch_bundle.execute_patch_bundle_generation(str(_root()), generate_bundle=True)
    after_content = workflow_path.read_text(encoding="utf-8") if workflow_path.exists() else ""
    assert before_content == after_content or not workflow_path.exists()


def test_no_git_push_in_git_command_results():
    result = patch_bundle.execute_patch_bundle_generation(str(_root()), generate_bundle=True)
    for cmd in result.get("git_command_results", []):
        argv = cmd.get("argv", [])
        assert argv[0] != "git" or argv[1] != "push"


def test_no_gh_workflow_run_in_git_command_results():
    result = patch_bundle.execute_patch_bundle_generation(str(_root()), generate_bundle=True)
    for cmd in result.get("git_command_results", []):
        argv = cmd.get("argv", [])
        assert not (argv[0] == "gh" and "workflow" in argv[1:])


# ── Test source commit hash constant ─────────────────────────────────────────

def test_source_commit_hash_is_valid_sha():
    assert len(patch_bundle.SOURCE_COMMIT_HASH) == 40
    assert all(c in "0123456789abcdef" for c in patch_bundle.SOURCE_COMMIT_HASH)


def test_source_commit_hash_matches_expected():
    assert patch_bundle.SOURCE_COMMIT_HASH == "94908556cc2ca66c219d361f424954945eee9e67"


# ── Test module enums exist and have expected values ─────────────────────────

def test_status_enum_has_generated():
    assert hasattr(patch_bundle.PatchBundleGenerationStatus, "GENERATED")


def test_decision_enum_has_generate_patch_and_bundle():
    assert hasattr(patch_bundle.PatchBundleGenerationDecision, "GENERATE_PATCH_AND_BUNDLE")


def test_artifact_enum_has_patch_and_bundle():
    assert hasattr(patch_bundle.PatchBundleArtifactType, "PATCH")
    assert hasattr(patch_bundle.PatchBundleArtifactType, "BUNDLE")


def test_risk_enum_has_low_and_medium():
    assert hasattr(patch_bundle.PatchBundleRiskLevel, "LOW")
    assert hasattr(patch_bundle.PatchBundleRiskLevel, "MEDIUM")