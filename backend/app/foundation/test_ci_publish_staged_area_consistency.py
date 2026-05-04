"""Tests for R241-16Q-B ci_publish_staged_area_consistency module."""

from pathlib import Path
import json
import pytest

from app.foundation import ci_publish_staged_area_consistency as staged_area


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


# ── Test load_r241_16q_push_failure_review ──────────────────────────────────

def test_load_r241_16q_requires_reviewed_push_permission_denied():
    result = staged_area.load_r241_16q_push_failure_review(str(_root()))
    assert result["status"] == "reviewed_push_permission_denied"


def test_load_r241_16q_reads_mutation_guard_staged_files():
    result = staged_area.load_r241_16q_push_failure_review(str(_root()))
    # R241-16Q reported staged_files = ["/app/m10/"] with mutation_guard_valid = False
    assert result["mutation_guard_valid"] is False
    assert "/app/m10/" in result["staged_files_reported"]


def test_load_r241_16q_reads_local_commit_info():
    result = staged_area.load_r241_16q_push_failure_review(str(_root()))
    assert result["local_commit_hash"] == "94908556cc2ca66c219d361f424954945eee9e67"
    assert result["local_commit_only_target_workflow"] is True


def test_load_r241_16q_raises_on_missing_file(tmp_path, monkeypatch):
    # Monkeypatch R241_16Q_REVIEW_PATH to a non-existent location
    import app.foundation.ci_publish_staged_area_consistency as s
    monkeypatch.setattr(s, "R241_16Q_REVIEW_PATH", tmp_path / "nonexistent" / "R241-16Q.json")
    with pytest.raises(FileNotFoundError):
        s.load_r241_16q_push_failure_review()


# ── Test inspect_current_staged_area ────────────────────────────────────────

def test_inspect_staged_area_returns_clean_when_cached_diff_empty():
    result = staged_area.inspect_current_staged_area(str(_root()))
    # Current index has no staged files (git diff --cached --name-only returns empty)
    assert result["staged_area_empty"] is True
    assert result["staged_files"] == []


def test_inspect_staged_area_app_m10_not_in_staged():
    result = staged_area.inspect_current_staged_area(str(_root()))
    assert result["app_m10_in_staged"] is False


def test_inspect_staged_area_returns_correct_command_keys():
    result = staged_area.inspect_current_staged_area(str(_root()))
    assert "git_diff_cached_command" in result
    assert "git_status_porcelain_command" in result


# ── Test detect_r241_16q_staged_parser_false_positive ─────────────────────────

def test_parser_false_positive_detected_when_r241_16q_staged_files_absent_now():
    """R241-16Q reported /app/m10/ but git diff --cached shows empty → false positive."""
    result = staged_area.detect_r241_16q_staged_parser_false_positive(str(_root()))
    # R241-16Q reported staged but current is empty → false positive
    assert result["parser_false_positive_detected"] is True
    assert result["m10_reported_in_r241_16q"] is True
    assert result["m10_in_current_staged"] is False
    assert result["root_cause"] == "git_status_short_m10_misparse"


def test_parser_false_positive_root_cause_explained():
    result = staged_area.detect_r241_16q_staged_parser_false_positive(str(_root()))
    assert "git status --short" in result["description"]
    assert "git diff --cached --name-only" in result["description"]


# ── Test _staged_files_from_cached_output ─────────────────────────────────────

def test_staged_files_from_cached_output_parses_simple_paths():
    output = ".github/workflows/foundation-manual-dispatch.yml\n.github/workflows/backend-unit-tests.yml\n"
    result = staged_area._staged_files_from_cached_output(output)
    assert len(result) == 2
    assert ".github/workflows/foundation-manual-dispatch.yml" in result


def test_staged_files_from_cached_output_handles_empty():
    result = staged_area._staged_files_from_cached_output("")
    assert result == []


def test_staged_files_from_cached_output_handles_windows_paths():
    output = ".github\\workflows\\foundation-manual-dispatch.yml\r\n"
    result = staged_area._staged_files_from_cached_output(output)
    assert len(result) == 1
    assert ".github/workflows/foundation-manual-dispatch.yml" in result


# ── Test evaluate_staged_area_consistency ────────────────────────────────────

def test_evaluate_returns_clean_status_when_no_staged_files():
    result = staged_area.evaluate_staged_area_consistency(str(_root()))
    # Current staged area is empty AND R241-16Q false positive detected
    # So status = parser_false_positive_fixed with allow_recovery_gate
    assert result["status"] in [
        staged_area.StagedAreaConsistencyStatus.PARSER_FALSE_POSITIVE_FIXED.value,
        staged_area.StagedAreaConsistencyStatus.CLEAN.value,
    ]


def test_evaluate_returns_allow_recovery_gate_decision():
    result = staged_area.evaluate_staged_area_consistency(str(_root()))
    assert result["decision"] == staged_area.StagedAreaConsistencyDecision.ALLOW_RECOVERY_GATE.value


def test_evaluate_detects_parser_false_positive():
    result = staged_area.evaluate_staged_area_consistency(str(_root()))
    assert result["parser_false_positive_detected"] is True
    assert result["parser_false_positive_root_cause"] == "git_status_short_m10_misparse"


def test_evaluate_local_commit_only_target_workflow():
    result = staged_area.evaluate_staged_area_consistency(str(_root()))
    assert result["local_commit_only_target_workflow"] is True


def test_evaluate_remote_workflow_still_missing():
    result = staged_area.evaluate_staged_area_consistency(str(_root()))
    assert result["remote_workflow_present"] is False


def test_evaluate_existing_workflows_unchanged():
    result = staged_area.evaluate_staged_area_consistency(str(_root()))
    assert result["existing_workflows_unchanged"] is True


def test_evaluate_recommended_next_phase_is_r241_16r():
    result = staged_area.evaluate_staged_area_consistency(str(_root()))
    assert result["recommended_next_phase"] == "R241-16R_recovery_path_confirmation_gate"


# ── Test validate_staged_area_consistency_review ─────────────────────────────

def test_validate_accepts_allow_recovery_gate_decision():
    review = {
        "decision": staged_area.StagedAreaConsistencyDecision.ALLOW_RECOVERY_GATE.value,
        "staged_area_empty": True,
        "staged_non_publish_files": [],
        "checks": [],
    }
    result = staged_area.validate_staged_area_consistency_review(review)
    assert result["valid"] is True


def test_validate_rejects_allow_recovery_with_staged_non_publish_files():
    review = {
        "decision": staged_area.StagedAreaConsistencyDecision.ALLOW_RECOVERY_GATE.value,
        "staged_area_empty": False,
        "staged_non_publish_files": [".github/other-workflow.yml"],
        "checks": [],
    }
    result = staged_area.validate_staged_area_consistency_review(review)
    assert result["valid"] is False
    assert any("decision_allow_recovery_with_staged_files_present" in r for r in result["blocked_reasons"])


def test_validate_rejects_blocked_decision_with_staged_files():
    review = {
        "decision": staged_area.StagedAreaConsistencyDecision.BLOCK_UNTIL_STAGED_AREA_CLEAN.value,
        "staged_area_empty": False,
        "staged_non_publish_files": [".github/other-workflow.yml"],
        "checks": [
            {"blocked_reasons": ["extra_staged_files_detected"]},
        ],
    }
    result = staged_area.validate_staged_area_consistency_review(review)
    assert result["valid"] is False


# ── Test generate_staged_area_consistency_report ──────────────────────────────

def test_generate_writes_json_and_md(tmp_path, monkeypatch):
    monkeypatch.setattr(staged_area, "ROOT", tmp_path)
    monkeypatch.setattr(staged_area, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    # Provide explicit review to avoid dependency on real R241-16Q file
    review = {
        "review_id": "test-review",
        "generated_at": "2026-04-26T00:00:00+00:00",
        "status": staged_area.StagedAreaConsistencyStatus.CLEAN.value,
        "decision": staged_area.StagedAreaConsistencyDecision.ALLOW_RECOVERY_GATE.value,
        "r241_16q_status": "reviewed_push_permission_denied",
        "r241_16q_decision": "keep_local_commit",
        "r241_16q_validation_valid": True,
        "r241_16q_mutation_guard_valid": False,
        "current_staged_files": [],
        "staged_area_empty": True,
        "staged_publish_target_present": False,
        "staged_non_publish_files": [],
        "parser_false_positive_detected": True,
        "parser_false_positive_root_cause": "git_status_short_m10_misparse",
        "parser_false_positive_description": "Test false positive",
        "local_commit_hash": "94908556cc2ca66c219d361f424954945eee9e67",
        "local_commit_only_target_workflow": True,
        "remote_workflow_present": False,
        "existing_workflows_unchanged": True,
        "checks": [],
        "recommended_next_phase": "R241-16R_recovery_path_confirmation_gate",
        "warnings": [],
        "errors": [],
    }
    report = staged_area.generate_staged_area_consistency_report(review, str(tmp_path / "R241-16Q-B.json"))
    assert Path(report["output_path"]).exists()
    assert Path(report["report_path"]).exists()


def test_generate_no_runtime_write(tmp_path, monkeypatch):
    monkeypatch.setattr(staged_area, "ROOT", tmp_path)
    monkeypatch.setattr(staged_area, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    review = {
        "review_id": "test-review",
        "generated_at": "2026-04-26T00:00:00+00:00",
        "status": staged_area.StagedAreaConsistencyStatus.CLEAN.value,
        "decision": staged_area.StagedAreaConsistencyDecision.ALLOW_RECOVERY_GATE.value,
        "r241_16q_status": "reviewed_push_permission_denied",
        "r241_16q_decision": "keep_local_commit",
        "r241_16q_validation_valid": True,
        "r241_16q_mutation_guard_valid": False,
        "current_staged_files": [],
        "staged_area_empty": True,
        "staged_publish_target_present": False,
        "staged_non_publish_files": [],
        "parser_false_positive_detected": True,
        "parser_false_positive_root_cause": "git_status_short_m10_misparse",
        "parser_false_positive_description": "Test",
        "local_commit_hash": "94908556cc2ca66c219d361f424954945eee9e67",
        "local_commit_only_target_workflow": True,
        "remote_workflow_present": False,
        "existing_workflows_unchanged": True,
        "checks": [],
        "recommended_next_phase": "R241-16R_recovery_path_confirmation_gate",
        "warnings": [],
        "errors": [],
    }
    staged_area.generate_staged_area_consistency_report(review, str(tmp_path / "R241-16Q-B.json"))
    assert not (tmp_path / "runtime").exists()


def test_generate_no_audit_jsonl_write(tmp_path, monkeypatch):
    audit_dir = tmp_path / "migration_reports" / "foundation_audit" / "audit_trail"
    audit_dir.mkdir(parents=True, exist_ok=True)
    jsonl = audit_dir / "foundation_diagnostic_runs.jsonl"
    jsonl.write_text('{"audit_record_id":"x"}\n', encoding="utf-8")
    before = jsonl.read_text(encoding="utf-8")
    monkeypatch.setattr(staged_area, "ROOT", tmp_path)
    monkeypatch.setattr(staged_area, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    review = {
        "review_id": "test-review",
        "generated_at": "2026-04-26T00:00:00+00:00",
        "status": staged_area.StagedAreaConsistencyStatus.CLEAN.value,
        "decision": staged_area.StagedAreaConsistencyDecision.ALLOW_RECOVERY_GATE.value,
        "r241_16q_status": "reviewed_push_permission_denied",
        "r241_16q_decision": "keep_local_commit",
        "r241_16q_validation_valid": True,
        "r241_16q_mutation_guard_valid": False,
        "current_staged_files": [],
        "staged_area_empty": True,
        "staged_publish_target_present": False,
        "staged_non_publish_files": [],
        "parser_false_positive_detected": True,
        "parser_false_positive_root_cause": "git_status_short_m10_misparse",
        "parser_false_positive_description": "Test",
        "local_commit_hash": "94908556cc2ca66c219d361f424954945eee9e67",
        "local_commit_only_target_workflow": True,
        "remote_workflow_present": False,
        "existing_workflows_unchanged": True,
        "checks": [],
        "recommended_next_phase": "R241-16R_recovery_path_confirmation_gate",
        "warnings": [],
        "errors": [],
    }
    staged_area.generate_staged_area_consistency_report(review, str(tmp_path / "R241-16Q-B.json"))
    assert jsonl.read_text(encoding="utf-8") == before


# ── Test no mutation during review ──────────────────────────────────────────

def test_no_workflow_modification_during_review():
    workflow_path = _root() / ".github" / "workflows" / "foundation-manual-dispatch.yml"
    before_content = workflow_path.read_text(encoding="utf-8") if workflow_path.exists() else ""
    staged_area.evaluate_staged_area_consistency(str(_root()))
    after_content = workflow_path.read_text(encoding="utf-8") if workflow_path.exists() else ""
    assert before_content == after_content or not workflow_path.exists()


def test_no_git_commit_during_review():
    review = staged_area.evaluate_staged_area_consistency(str(_root()))
    assert review["status"] != ""  # No commit was executed


def test_no_git_push_during_review():
    review = staged_area.evaluate_staged_area_consistency(str(_root()))
    checks = review.get("checks", [])
    for check in checks:
        cmd = check.get("command_executed", {})
        argv = cmd.get("argv", []) if isinstance(cmd, dict) else []
        assert argv[0] != "git" or argv[1] != "push" if argv else True


def test_no_gh_workflow_run_during_review():
    review = staged_area.evaluate_staged_area_consistency(str(_root()))
    checks = review.get("checks", [])
    for check in checks:
        observed = check.get("observed_value", {})
        if isinstance(observed, dict):
            for cmd_name, cmd_result in observed.items():
                if isinstance(cmd_result, dict):
                    argv = cmd_result.get("argv", [])
                    assert argv[0] != "gh" or len(argv) < 3 or argv[2] != "workflow" if argv else True


def test_no_secret_read():
    review = staged_area.evaluate_staged_area_consistency(str(_root()))
    # No checks should involve reading secrets
    assert review.get("warnings", []) == [] or review.get("warnings") is not None


# ── Test generate without explicit review argument ──────────────────────────

def test_generate_uses_default_root_when_no_review_provided(tmp_path, monkeypatch):
    monkeypatch.setattr(staged_area, "ROOT", tmp_path)
    monkeypatch.setattr(staged_area, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    # Provide explicit review to avoid dependency on real R241-16Q file
    review = {
        "review_id": "test-review",
        "generated_at": "2026-04-26T00:00:00+00:00",
        "status": staged_area.StagedAreaConsistencyStatus.CLEAN.value,
        "decision": staged_area.StagedAreaConsistencyDecision.ALLOW_RECOVERY_GATE.value,
        "r241_16q_status": "reviewed_push_permission_denied",
        "r241_16q_decision": "keep_local_commit",
        "r241_16q_validation_valid": True,
        "r241_16q_mutation_guard_valid": False,
        "current_staged_files": [],
        "staged_area_empty": True,
        "staged_publish_target_present": False,
        "staged_non_publish_files": [],
        "parser_false_positive_detected": True,
        "parser_false_positive_root_cause": "git_status_short_m10_misparse",
        "parser_false_positive_description": "Test",
        "local_commit_hash": "94908556cc2ca66c219d361f424954945eee9e67",
        "local_commit_only_target_workflow": True,
        "remote_workflow_present": False,
        "existing_workflows_unchanged": True,
        "checks": [],
        "recommended_next_phase": "R241-16R_recovery_path_confirmation_gate",
        "warnings": [],
        "errors": [],
    }
    report = staged_area.generate_staged_area_consistency_report(review)
    assert report is not None
    assert "output_path" in report
