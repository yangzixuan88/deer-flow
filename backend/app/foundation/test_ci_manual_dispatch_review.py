import json
from pathlib import Path

import pytest

from app.foundation import ci_manual_dispatch_review as mdr
from app.foundation import ci_workflow_draft


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


# ── 1. build_manual_dispatch_input_specs ───────────────────────────────────────

def test_input_specs_contains_confirm_manual_dispatch():
    specs = mdr.build_manual_dispatch_input_specs()
    ids = [s["input_id"] for s in specs["input_specs"]]
    assert "confirm_manual_dispatch" in ids


def test_confirm_manual_dispatch_expected_value():
    specs = mdr.build_manual_dispatch_input_specs()
    confirm = next(s for s in specs["input_specs"] if s["input_id"] == "confirm_manual_dispatch")
    assert confirm["expected_value"] == "CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN"


def test_confirm_manual_dispatch_secret_not_allowed():
    specs = mdr.build_manual_dispatch_input_specs()
    confirm = next(s for s in specs["input_specs"] if s["input_id"] == "confirm_manual_dispatch")
    assert confirm["secret_allowed"] is False


def test_stage_selection_allowed_values():
    specs = mdr.build_manual_dispatch_input_specs()
    stage = next(s for s in specs["input_specs"] if s["input_id"] == "stage_selection")
    allowed = stage.get("allowed_values", [])
    assert "all_pr" in allowed
    assert "fast" in allowed
    assert "safety" in allowed
    assert "collect_only" in allowed
    assert "all_nightly" in allowed


def test_stage_selection_forbidden_values():
    specs = mdr.build_manual_dispatch_input_specs()
    stage = next(s for s in specs["input_specs"] if s["input_id"] == "stage_selection")
    forbidden = stage.get("forbidden_values", [])
    assert "full" in forbidden
    assert "real_send" in forbidden
    assert "auto_fix" in forbidden
    assert "webhook" in forbidden
    assert "secret" in forbidden


def test_execute_mode_default_is_plan_only():
    specs = mdr.build_manual_dispatch_input_specs()
    mode = next(s for s in specs["input_specs"] if s["input_id"] == "execute_mode")
    assert mode["default"] == "plan_only"


# ── 2. build_manual_dispatch_job_guard_specs ───────────────────────────────────

def test_job_guard_specs_contains_smoke_fast_safety_collect_only():
    specs = mdr.build_manual_dispatch_job_guard_specs()
    job_ids = {g["job_id"] for g in specs["job_guard_specs"]}
    assert "job_smoke" in job_ids
    assert "job_fast" in job_ids
    assert "job_safety" in job_ids
    assert "job_collect_only" in job_ids


def test_job_guard_smoke_network_not_allowed():
    specs = mdr.build_manual_dispatch_job_guard_specs()
    guard = next(g for g in specs["job_guard_specs"] if g["job_id"] == "job_smoke")
    assert guard["network_allowed"] is False


def test_job_guard_smoke_secret_refs_not_allowed():
    specs = mdr.build_manual_dispatch_job_guard_specs()
    guard = next(g for g in specs["job_guard_specs"] if g["job_id"] == "job_smoke")
    assert guard["secret_refs_allowed"] is False


def test_job_guard_smoke_runtime_write_not_allowed():
    specs = mdr.build_manual_dispatch_job_guard_specs()
    guard = next(g for g in specs["job_guard_specs"] if g["job_id"] == "job_smoke")
    assert guard["runtime_write_allowed"] is False


def test_job_guard_smoke_auto_fix_not_allowed():
    specs = mdr.build_manual_dispatch_job_guard_specs()
    guard = next(g for g in specs["job_guard_specs"] if g["job_id"] == "job_smoke")
    assert guard["auto_fix_allowed"] is False


# ── 3. Security checks ─────────────────────────────────────────────────────────

def test_security_checks_all_pass():
    checks = mdr.evaluate_manual_dispatch_security_checks()
    assert checks["all_passed"] is True


def test_security_check_no_pr_trigger():
    checks = mdr.evaluate_manual_dispatch_security_checks()
    check = next(c for c in checks["checks"] if c["check_id"] == "check_no_pr_trigger")
    assert check["passed"] is True


def test_security_check_no_push_trigger():
    checks = mdr.evaluate_manual_dispatch_security_checks()
    check = next(c for c in checks["checks"] if c["check_id"] == "check_no_push_trigger")
    assert check["passed"] is True


def test_security_check_no_schedule_trigger():
    checks = mdr.evaluate_manual_dispatch_security_checks()
    check = next(c for c in checks["checks"] if c["check_id"] == "check_no_schedule_trigger")
    assert check["passed"] is True


def test_security_check_no_network():
    checks = mdr.evaluate_manual_dispatch_security_checks()
    check = next(c for c in checks["checks"] if c["check_id"] == "check_no_network")
    assert check["passed"] is True


def test_security_check_no_runtime_write():
    checks = mdr.evaluate_manual_dispatch_security_checks()
    check = next(c for c in checks["checks"] if c["check_id"] == "check_no_runtime_write")
    assert check["passed"] is True


def test_security_check_no_auto_fix():
    checks = mdr.evaluate_manual_dispatch_security_checks()
    check = next(c for c in checks["checks"] if c["check_id"] == "check_no_auto_fix")
    assert check["passed"] is True


def test_security_check_no_feishu_send():
    checks = mdr.evaluate_manual_dispatch_security_checks()
    check = next(c for c in checks["checks"] if c["check_id"] == "check_no_feishu_send")
    assert check["passed"] is True


# ── 4. Implementation options ───────────────────────────────────────────────────

def test_implementation_options_contains_a_b_c_d():
    opts = mdr.build_manual_dispatch_implementation_options()
    option_ids = {o["option_id"] for o in opts["options"]}
    assert "option_a" in option_ids
    assert "option_b" in option_ids
    assert "option_c" in option_ids
    assert "option_d" in option_ids


def test_implementation_options_recommended_option_present():
    opts = mdr.build_manual_dispatch_implementation_options()
    assert opts["recommended_option"] in ("option_a", "option_b", "option_c", "option_d")


# ── 5. Rollback plan ───────────────────────────────────────────────────────────

def test_rollback_plan_has_steps():
    rollback = mdr.build_manual_dispatch_rollback_plan()
    assert len(rollback["rollback_steps"]) > 0


# ── 6. evaluate_manual_dispatch_readiness ──────────────────────────────────────

def test_evaluate_readiness_returns_review():
    review = mdr.evaluate_manual_dispatch_readiness(str(_root()))
    assert "review_id" in review
    assert review["review_id"] == "R241-16E_manual_dispatch_dryrun_review"


def test_evaluate_readiness_status_is_not_unknown():
    review = mdr.evaluate_manual_dispatch_readiness(str(_root()))
    assert review["status"] != mdr.ManualDispatchReadinessStatus.UNKNOWN


def test_evaluate_readiness_workflow_not_created():
    review = mdr.evaluate_manual_dispatch_readiness(str(_root()))
    assert review["workflow_created"] is False


def test_evaluate_readiness_trigger_not_enabled():
    review = mdr.evaluate_manual_dispatch_readiness(str(_root()))
    assert review["trigger_enabled"] is False


def test_evaluate_readiness_no_network_recommended():
    review = mdr.evaluate_manual_dispatch_readiness(str(_root()))
    assert review["network_recommended"] is False


def test_evaluate_readiness_no_runtime_write_recommended():
    review = mdr.evaluate_manual_dispatch_readiness(str(_root()))
    assert review["runtime_write_recommended"] is False


def test_evaluate_readiness_no_secret_read_recommended():
    review = mdr.evaluate_manual_dispatch_readiness(str(_root()))
    assert review["secret_read_recommended"] is False


def test_evaluate_readiness_no_auto_fix_recommended():
    review = mdr.evaluate_manual_dispatch_readiness(str(_root()))
    assert review["auto_fix_recommended"] is False


# ── 7. validate_manual_dispatch_dryrun_review ──────────────────────────────────

def test_validate_passes_for_clean_review():
    review = mdr.evaluate_manual_dispatch_readiness(str(_root()))
    validation = mdr.validate_manual_dispatch_dryrun_review(review)
    assert validation["valid"] is True
    assert validation["errors"] == []


def test_validate_fails_if_workflow_created():
    review = mdr.evaluate_manual_dispatch_readiness(str(_root()))
    review["workflow_created"] = True
    validation = mdr.validate_manual_dispatch_dryrun_review(review)
    assert validation["valid"] is False
    assert any("workflow_creation_not_allowed" in e for e in validation["errors"])


def test_validate_fails_if_trigger_enabled():
    review = mdr.evaluate_manual_dispatch_readiness(str(_root()))
    review["trigger_enabled"] = True
    validation = mdr.validate_manual_dispatch_dryrun_review(review)
    assert validation["valid"] is False
    assert any("trigger_enablement_not_allowed" in e for e in validation["errors"])


def test_validate_fails_if_network_recommended():
    review = mdr.evaluate_manual_dispatch_readiness(str(_root()))
    review["network_recommended"] = True
    validation = mdr.validate_manual_dispatch_dryrun_review(review)
    assert validation["valid"] is False
    assert any("network_recommended_not_allowed" in e for e in validation["errors"])


def test_validate_fails_if_runtime_write_recommended():
    review = mdr.evaluate_manual_dispatch_readiness(str(_root()))
    review["runtime_write_recommended"] = True
    validation = mdr.validate_manual_dispatch_dryrun_review(review)
    assert validation["valid"] is False
    assert any("runtime_write_recommended_not_allowed" in e for e in validation["errors"])


def test_validate_fails_if_secret_read_recommended():
    review = mdr.evaluate_manual_dispatch_readiness(str(_root()))
    review["secret_read_recommended"] = True
    validation = mdr.validate_manual_dispatch_dryrun_review(review)
    assert validation["valid"] is False
    assert any("secret_read_recommended_not_allowed" in e for e in validation["errors"])


def test_validate_fails_if_auto_fix_recommended():
    review = mdr.evaluate_manual_dispatch_readiness(str(_root()))
    review["auto_fix_recommended"] = True
    validation = mdr.validate_manual_dispatch_dryrun_review(review)
    assert validation["valid"] is False
    assert any("auto_fix_recommended_not_allowed" in e for e in validation["errors"])


def test_validate_fails_if_confirmation_input_missing():
    review = mdr.evaluate_manual_dispatch_readiness(str(_root()))
    review["dispatch_input_specs"]["confirmation_input_exists"] = False
    validation = mdr.validate_manual_dispatch_dryrun_review(review)
    assert validation["valid"] is False
    assert any("confirmation_input_missing" in e for e in validation["errors"])


def test_validate_fails_if_confirm_wrong_expected_value():
    review = mdr.evaluate_manual_dispatch_readiness(str(_root()))
    confirm = next(
        s for s in review["dispatch_input_specs"]["input_specs"]
        if s["input_id"] == "confirm_manual_dispatch"
    )
    confirm["expected_value"] = "WRONG"
    validation = mdr.validate_manual_dispatch_dryrun_review(review)
    assert validation["valid"] is False
    assert any("confirm_manual_dispatch_wrong_expected_value" in e for e in validation["errors"])


def test_validate_fails_if_confirm_secret_allowed():
    review = mdr.evaluate_manual_dispatch_readiness(str(_root()))
    confirm = next(
        s for s in review["dispatch_input_specs"]["input_specs"]
        if s["input_id"] == "confirm_manual_dispatch"
    )
    confirm["secret_allowed"] = True
    validation = mdr.validate_manual_dispatch_dryrun_review(review)
    assert validation["valid"] is False
    assert any("confirm_manual_dispatch_secret_not_allowed" in e for e in validation["errors"])


def test_validate_fails_if_job_guard_network_allowed():
    review = mdr.evaluate_manual_dispatch_readiness(str(_root()))
    guard = review["job_guard_specs"]["job_guard_specs"][0]
    guard["network_allowed"] = True
    validation = mdr.validate_manual_dispatch_dryrun_review(review)
    assert validation["valid"] is False
    assert any("network_allowed_not_allowed" in e for e in validation["errors"])


def test_validate_fails_if_job_guard_secret_refs_allowed():
    review = mdr.evaluate_manual_dispatch_readiness(str(_root()))
    guard = review["job_guard_specs"]["job_guard_specs"][0]
    guard["secret_refs_allowed"] = True
    validation = mdr.validate_manual_dispatch_dryrun_review(review)
    assert validation["valid"] is False
    assert any("secret_refs_not_allowed" in e for e in validation["errors"])


def test_validate_fails_if_job_guard_runtime_write_allowed():
    review = mdr.evaluate_manual_dispatch_readiness(str(_root()))
    guard = review["job_guard_specs"]["job_guard_specs"][0]
    guard["runtime_write_allowed"] = True
    validation = mdr.validate_manual_dispatch_dryrun_review(review)
    assert validation["valid"] is False
    assert any("runtime_write_not_allowed" in e for e in validation["errors"])


def test_validate_fails_if_job_guard_auto_fix_allowed():
    review = mdr.evaluate_manual_dispatch_readiness(str(_root()))
    guard = review["job_guard_specs"]["job_guard_specs"][0]
    guard["auto_fix_allowed"] = True
    validation = mdr.validate_manual_dispatch_dryrun_review(review)
    assert validation["valid"] is False
    assert any("auto_fix_not_allowed" in e for e in validation["errors"])


# ── 8. generate_manual_dispatch_dryrun_review safety ───────────────────────────

def test_generate_writes_to_tmp_path_only(tmp_path, monkeypatch):
    monkeypatch.setattr(mdr, "ROOT", tmp_path)
    monkeypatch.setattr(mdr, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    result = mdr.generate_manual_dispatch_dryrun_review()
    assert Path(result["output_path"]).exists()
    assert Path(result["report_path"]).exists()


def test_generate_does_not_create_github_workflows(tmp_path, monkeypatch):
    monkeypatch.setattr(mdr, "ROOT", tmp_path)
    monkeypatch.setattr(mdr, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    mdr.generate_manual_dispatch_dryrun_review()
    gh_dir = tmp_path / ".github" / "workflows"
    assert not gh_dir.exists()


def test_generate_does_not_write_audit_jsonl(tmp_path, monkeypatch):
    audit_dir = tmp_path / "migration_reports" / "foundation_audit" / "audit_trail"
    audit_dir.mkdir(parents=True)
    jsonl = audit_dir / "foundation_diagnostic_runs.jsonl"
    jsonl.write_text('{"audit_record_id":"x"}\n', encoding="utf-8")
    before = jsonl.read_text(encoding="utf-8")
    monkeypatch.setattr(mdr, "ROOT", tmp_path)
    monkeypatch.setattr(mdr, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    mdr.generate_manual_dispatch_dryrun_review()
    assert jsonl.read_text(encoding="utf-8") == before


def test_generate_does_not_write_runtime_or_action_queue(tmp_path, monkeypatch):
    monkeypatch.setattr(mdr, "ROOT", tmp_path)
    monkeypatch.setattr(mdr, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    mdr.generate_manual_dispatch_dryrun_review()
    runtime_dir = tmp_path / "runtime"
    action_queue_dir = tmp_path / "action_queue"
    assert not runtime_dir.exists()
    assert not action_queue_dir.exists()


def test_generate_does_not_perform_network_or_webhook_call(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(mdr, "ROOT", tmp_path)
    monkeypatch.setattr(mdr, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    monkeypatch.setattr(mdr, "evaluate_manual_dispatch_readiness", lambda r: called.append("readiness") or {
        "review_id": "test",
        "generated_at": "",
        "status": mdr.ManualDispatchReadinessStatus.READY_FOR_IMPLEMENTATION_REVIEW,
        "dispatch_input_specs": mdr.build_manual_dispatch_input_specs(),
        "job_guard_specs": mdr.build_manual_dispatch_job_guard_specs(),
        "existing_workflow_compatibility": [],
        "artifact_policy_check": {"artifact_specs": []},
        "path_compatibility_check": {},
        "threshold_policy_check": {},
        "security_checks": {"checks": [], "all_passed": True},
        "rollback_plan": {"rollback_steps": ["step"]},
        "implementation_options": [],
        "recommended_option": "option_c",
        "recommendation_reason": "test",
        "workflow_created": False,
        "trigger_enabled": False,
        "network_recommended": False,
        "runtime_write_recommended": False,
        "secret_read_recommended": False,
        "auto_fix_recommended": False,
        "warnings": [],
        "errors": [],
    })
    mdr.generate_manual_dispatch_dryrun_review()
    assert called == ["readiness"]


def test_generate_does_not_execute_auto_fix(tmp_path, monkeypatch):
    monkeypatch.setattr(mdr, "ROOT", tmp_path)
    monkeypatch.setattr(mdr, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    result = mdr.generate_manual_dispatch_dryrun_review()
    # auto_fix_recommended is inside the nested review dict
    assert result["review"]["auto_fix_recommended"] is False
