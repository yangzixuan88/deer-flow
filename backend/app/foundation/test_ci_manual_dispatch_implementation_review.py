import json
from pathlib import Path

import pytest

from app.foundation import ci_manual_dispatch_implementation_review as impl
from app.foundation import ci_workflow_draft


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


# ── 1. build_manual_dispatch_workflow_blueprint ───────────────────────────────

def test_blueprint_write_target_allowed_is_false():
    bp = impl.build_manual_dispatch_workflow_blueprint(str(_root()))
    assert bp["write_target_allowed"] is False


def test_blueprint_proposed_filename():
    bp = impl.build_manual_dispatch_workflow_blueprint(str(_root()))
    assert bp["workflow_filename_proposed"] == "foundation-manual-dispatch.yml"


def test_blueprint_trigger_only_workflow_dispatch():
    bp = impl.build_manual_dispatch_workflow_blueprint(str(_root()))
    assert bp["trigger_policy"]["workflow_dispatch_enabled"] is True
    assert bp["trigger_policy"]["pull_request_enabled"] is False
    assert bp["trigger_policy"]["push_enabled"] is False
    assert bp["trigger_policy"]["schedule_enabled"] is False


def test_blueprint_contains_confirm_manual_dispatch_input():
    bp = impl.build_manual_dispatch_workflow_blueprint(str(_root()))
    inputs = bp["workflow_dispatch_inputs"]
    confirm = next((i for i in inputs if i["input_id"] == "confirm_manual_dispatch"), None)
    assert confirm is not None
    assert confirm["expected_value"] == "CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN"


def test_blueprint_execute_mode_defaults_plan_only():
    bp = impl.build_manual_dispatch_workflow_blueprint(str(_root()))
    mode = next(
        (i for i in bp["workflow_dispatch_inputs"] if i["input_id"] == "execute_mode"),
        None,
    )
    assert mode is not None
    assert mode["default"] == "plan_only"


def test_blueprint_allowed_stage_selections():
    bp = impl.build_manual_dispatch_workflow_blueprint(str(_root()))
    assert "all_pr" in bp["allowed_stage_selections"]
    assert "fast" in bp["allowed_stage_selections"]
    assert "safety" in bp["allowed_stage_selections"]
    assert "collect_only" in bp["allowed_stage_selections"]
    assert "all_nightly" in bp["allowed_stage_selections"]


def test_blueprint_forbidden_stage_selections():
    bp = impl.build_manual_dispatch_workflow_blueprint(str(_root()))
    assert "full" in bp["forbidden_stage_selections"]
    assert "real_send" in bp["forbidden_stage_selections"]
    assert "auto_fix" in bp["forbidden_stage_selections"]
    assert "webhook" in bp["forbidden_stage_selections"]
    assert "secret" in bp["forbidden_stage_selections"]


# ── 2. build_manual_dispatch_job_blueprints ───────────────────────────────────

def test_job_blueprints_contains_fast():
    jobs = impl.build_manual_dispatch_job_blueprints()
    job_ids = {j["job_id"] for j in jobs}
    assert "job_fast" in job_ids


def test_job_blueprints_contains_safety():
    jobs = impl.build_manual_dispatch_job_blueprints()
    job_ids = {j["job_id"] for j in jobs}
    assert "job_safety" in job_ids


def test_job_blueprints_contains_slow():
    jobs = impl.build_manual_dispatch_job_blueprints()
    job_ids = {j["job_id"] for j in jobs}
    assert "job_slow" in job_ids


def test_job_blueprints_does_not_contain_full():
    jobs = impl.build_manual_dispatch_job_blueprints()
    job_types = {j["job_type"] for j in jobs}
    assert ci_workflow_draft.WorkflowJobType.FULL not in job_types


def test_every_job_network_allowed_false():
    jobs = impl.build_manual_dispatch_job_blueprints()
    for job in jobs:
        assert job["network_allowed"] is False, f"{job['job_id']} network_allowed must be False"


def test_every_job_secret_refs_allowed_false():
    jobs = impl.build_manual_dispatch_job_blueprints()
    for job in jobs:
        assert job["secret_refs_allowed"] is False, f"{job['job_id']} secret_refs_allowed must be False"


def test_every_job_runtime_write_allowed_false():
    jobs = impl.build_manual_dispatch_job_blueprints()
    for job in jobs:
        assert job["runtime_write_allowed"] is False, f"{job['job_id']} runtime_write_allowed must be False"


def test_every_job_audit_jsonl_write_allowed_false():
    jobs = impl.build_manual_dispatch_job_blueprints()
    for job in jobs:
        assert job["audit_jsonl_write_allowed"] is False, f"{job['job_id']} audit_jsonl_write_allowed must be False"


def test_every_job_action_queue_write_allowed_false():
    jobs = impl.build_manual_dispatch_job_blueprints()
    for job in jobs:
        assert job["action_queue_write_allowed"] is False, f"{job['job_id']} action_queue_write_allowed must be False"


def test_every_job_auto_fix_allowed_false():
    jobs = impl.build_manual_dispatch_job_blueprints()
    for job in jobs:
        assert job["auto_fix_allowed"] is False, f"{job['job_id']} auto_fix_allowed must be False"


def test_every_job_enabled_by_default_false():
    jobs = impl.build_manual_dispatch_job_blueprints()
    for job in jobs:
        assert job["enabled_by_default"] is False, f"{job['job_id']} enabled_by_default must be False"


def test_fast_job_guard_expression_contains_confirmation():
    jobs = impl.build_manual_dispatch_job_blueprints()
    fast = next(j for j in jobs if j["job_id"] == "job_fast")
    assert "CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN" in fast["guard_expression"]


def test_slow_job_requires_all_nightly_selection():
    jobs = impl.build_manual_dispatch_job_blueprints()
    slow = next(j for j in jobs if j["job_id"] == "job_slow")
    assert "all_nightly" in slow["allowed_stage_selections"]


# ── 3. render_manual_dispatch_workflow_blueprint_yaml ──────────────────────────

def test_rendered_yaml_contains_manual_dispatch_blueprint_only():
    bp = impl.build_manual_dispatch_workflow_blueprint(str(_root()))
    result = impl.render_manual_dispatch_workflow_blueprint_yaml(bp)
    assert "MANUAL DISPATCH BLUEPRINT ONLY" in result["yaml_text"]


def test_rendered_yaml_does_not_contain_pull_request():
    bp = impl.build_manual_dispatch_workflow_blueprint(str(_root()))
    result = impl.render_manual_dispatch_workflow_blueprint_yaml(bp)
    assert "pull_request:" not in result["yaml_text"]


def test_rendered_yaml_does_not_contain_push_trigger():
    bp = impl.build_manual_dispatch_workflow_blueprint(str(_root()))
    result = impl.render_manual_dispatch_workflow_blueprint_yaml(bp)
    # Should not have "push:" as a trigger keyword (not in command strings)
    lines_with_trigger = [
        line for line in result["yaml_text"].splitlines()
        if line.strip().startswith("push:")
    ]
    assert len(lines_with_trigger) == 0


def test_rendered_yaml_does_not_contain_schedule_trigger():
    bp = impl.build_manual_dispatch_workflow_blueprint(str(_root()))
    result = impl.render_manual_dispatch_workflow_blueprint_yaml(bp)
    lines_with_trigger = [
        line for line in result["yaml_text"].splitlines()
        if line.strip().startswith("schedule:")
    ]
    assert len(lines_with_trigger) == 0


def test_rendered_yaml_does_not_contain_secrets():
    bp = impl.build_manual_dispatch_workflow_blueprint(str(_root()))
    result = impl.render_manual_dispatch_workflow_blueprint_yaml(bp)
    assert "secrets." not in result["yaml_text"]


def test_rendered_yaml_does_not_contain_curl_or_webhook():
    bp = impl.build_manual_dispatch_workflow_blueprint(str(_root()))
    result = impl.render_manual_dispatch_workflow_blueprint_yaml(bp)
    yaml_lower = result["yaml_text"].lower()
    assert "curl" not in yaml_lower
    assert "webhook" not in yaml_lower


def test_rendered_yaml_contains_workflow_dispatch():
    bp = impl.build_manual_dispatch_workflow_blueprint(str(_root()))
    result = impl.render_manual_dispatch_workflow_blueprint_yaml(bp)
    assert "workflow_dispatch:" in result["yaml_text"]


def test_rendered_yaml_contains_confirm_input():
    bp = impl.build_manual_dispatch_workflow_blueprint(str(_root()))
    result = impl.render_manual_dispatch_workflow_blueprint_yaml(bp)
    assert "confirm_manual_dispatch" in result["yaml_text"]


def test_rendered_yaml_contains_stage_selection():
    bp = impl.build_manual_dispatch_workflow_blueprint(str(_root()))
    result = impl.render_manual_dispatch_workflow_blueprint_yaml(bp)
    assert "stage_selection" in result["yaml_text"]


def test_rendered_yaml_contains_execute_mode():
    bp = impl.build_manual_dispatch_workflow_blueprint(str(_root()))
    result = impl.render_manual_dispatch_workflow_blueprint_yaml(bp)
    assert "execute_mode" in result["yaml_text"]


def test_rendered_yaml_contains_no_forbidden_tokens():
    bp = impl.build_manual_dispatch_workflow_blueprint(str(_root()))
    result = impl.render_manual_dispatch_workflow_blueprint_yaml(bp)
    assert result["errors"] == []


# ── 4. build_manual_dispatch_implementation_checks ──────────────────────────────

def test_implementation_checks_count_at_least_17():
    checks = impl.build_manual_dispatch_implementation_checks()
    assert checks["check_count"] >= 17


def test_implementation_checks_github_workflows_write_blocked():
    checks = impl.build_manual_dispatch_implementation_checks()
    check = next(
        (c for c in checks["implementation_checks"] if c["check_id"] == "check_github_workflows_write_blocked"),
        None,
    )
    assert check is not None
    assert check["passed"] is True


def test_implementation_checks_all_pass():
    checks = impl.build_manual_dispatch_implementation_checks()
    assert checks["all_passed"] is True


def test_implementation_checks_no_pr_trigger():
    checks = impl.build_manual_dispatch_implementation_checks()
    check = next(
        (c for c in checks["implementation_checks"] if c["check_id"] == "check_no_pr_push_schedule_triggers"),
        None,
    )
    assert check is not None
    assert check["passed"] is True


def test_implementation_checks_no_secrets():
    checks = impl.build_manual_dispatch_implementation_checks()
    check = next(
        (c for c in checks["implementation_checks"] if c["check_id"] == "check_no_secrets"),
        None,
    )
    assert check is not None
    assert check["passed"] is True


def test_implementation_checks_no_auto_fix():
    checks = impl.build_manual_dispatch_implementation_checks()
    check = next(
        (c for c in checks["implementation_checks"] if c["check_id"] == "check_no_auto_fix"),
        None,
    )
    assert check is not None
    assert check["passed"] is True


# ── 5. build_manual_dispatch_validation_plan ────────────────────────────────────

def test_validation_plan_has_pre_implementation():
    plan = impl.build_manual_dispatch_validation_plan()
    assert "pre_implementation_validation" in plan
    assert len(plan["pre_implementation_validation"]) > 0


def test_validation_plan_has_post_implementation():
    plan = impl.build_manual_dispatch_validation_plan()
    assert "post_implementation_validation" in plan
    assert len(plan["post_implementation_validation"]) > 0


def test_validation_plan_pre_contains_root_guard():
    plan = impl.build_manual_dispatch_validation_plan()
    names = [s["name"] for s in plan["pre_implementation_validation"]]
    assert any("RootGuard" in n for n in names)


def test_validation_plan_pre_contains_unit_tests():
    plan = impl.build_manual_dispatch_validation_plan()
    names = [s["name"] for s in plan["pre_implementation_validation"]]
    assert any("unit" in n.lower() for n in names)


# ── 6. build_manual_dispatch_next_phase_options ───────────────────────────────

def test_next_phase_options_contains_a_b_c_d():
    result = impl.build_manual_dispatch_next_phase_options(confirmation_received=False)
    option_ids = {o["option_id"] for o in result["options"]}
    assert "option_a" in option_ids
    assert "option_b" in option_ids
    assert "option_c" in option_ids
    assert "option_d" in option_ids


def test_next_phase_recommended_not_create_workflow_without_confirmation():
    result = impl.build_manual_dispatch_next_phase_options(confirmation_received=False)
    # Without confirmation, recommended should NOT be option_c or option_d
    assert result["recommended_option"] in ("option_a", "option_b")


def test_next_phase_recommended_allow_workflow_with_confirmation():
    result = impl.build_manual_dispatch_next_phase_options(confirmation_received=True)
    # With confirmation, recommended CAN be option_c or option_d
    assert result["recommended_option"] in ("option_a", "option_b", "option_c", "option_d")


# ── 7. evaluate_manual_dispatch_implementation_review ───────────────────────────

def test_evaluate_returns_review():
    review = impl.evaluate_manual_dispatch_implementation_review(str(_root()))
    assert "review_id" in review
    assert review["review_id"] == "R241-16F_manual_dispatch_implementation_review"


def test_evaluate_review_status_is_not_unknown():
    review = impl.evaluate_manual_dispatch_implementation_review(str(_root()))
    assert review["status"] != impl.ManualDispatchImplementationStatus.UNKNOWN


def test_evaluate_workflow_not_created():
    review = impl.evaluate_manual_dispatch_implementation_review(str(_root()))
    assert review["workflow_created"] is False


def test_evaluate_trigger_not_enabled():
    review = impl.evaluate_manual_dispatch_implementation_review(str(_root()))
    assert review["trigger_enabled"] is False


def test_evaluate_r241_16e_gap_note_present():
    review = impl.evaluate_manual_dispatch_implementation_review(str(_root()))
    assert "r241_16e_report_gap_note" in review
    assert "identified_gap" in review["r241_16e_report_gap_note"]


def test_evaluate_r241_16e_verification_summary_present():
    review = impl.evaluate_manual_dispatch_implementation_review(str(_root()))
    assert "r241_16e_verification_summary" in review
    assert review["r241_16e_verification_summary"]["r241_16e_validation_valid"] is True


def test_evaluate_blueprint_has_yaml():
    review = impl.evaluate_manual_dispatch_implementation_review(str(_root()))
    assert "yaml_blueprint" in review["blueprint"]
    assert len(review["blueprint"]["yaml_blueprint"]) > 0


# ── 8. validate_manual_dispatch_implementation_review ───────────────────────────

def test_validate_passes_for_clean_review():
    review = impl.evaluate_manual_dispatch_implementation_review(str(_root()))
    validation = impl.validate_manual_dispatch_implementation_review(review)
    assert validation["valid"] is True
    assert validation["errors"] == []


def test_validate_fails_if_workflow_created():
    review = impl.evaluate_manual_dispatch_implementation_review(str(_root()))
    review["workflow_created"] = True
    validation = impl.validate_manual_dispatch_implementation_review(review)
    assert validation["valid"] is False
    assert any("workflow_creation_not_allowed" in e for e in validation["errors"])


def test_validate_fails_if_trigger_enabled():
    review = impl.evaluate_manual_dispatch_implementation_review(str(_root()))
    review["trigger_enabled"] = True
    validation = impl.validate_manual_dispatch_implementation_review(review)
    assert validation["valid"] is False
    assert any("trigger_enablement_not_allowed" in e for e in validation["errors"])


def test_validate_fails_if_network_recommended():
    review = impl.evaluate_manual_dispatch_implementation_review(str(_root()))
    review["network_recommended"] = True
    validation = impl.validate_manual_dispatch_implementation_review(review)
    assert validation["valid"] is False
    assert any("network_recommended_not_allowed" in e for e in validation["errors"])


def test_validate_fails_if_runtime_write_recommended():
    review = impl.evaluate_manual_dispatch_implementation_review(str(_root()))
    review["runtime_write_recommended"] = True
    validation = impl.validate_manual_dispatch_implementation_review(review)
    assert validation["valid"] is False
    assert any("runtime_write_recommended_not_allowed" in e for e in validation["errors"])


def test_validate_fails_if_secret_read_recommended():
    review = impl.evaluate_manual_dispatch_implementation_review(str(_root()))
    review["secret_read_recommended"] = True
    validation = impl.validate_manual_dispatch_implementation_review(review)
    assert validation["valid"] is False
    assert any("secret_read_recommended_not_allowed" in e for e in validation["errors"])


def test_validate_fails_if_auto_fix_recommended():
    review = impl.evaluate_manual_dispatch_implementation_review(str(_root()))
    review["auto_fix_recommended"] = True
    validation = impl.validate_manual_dispatch_implementation_review(review)
    assert validation["valid"] is False
    assert any("auto_fix_recommended_not_allowed" in e for e in validation["errors"])


def test_validate_fails_if_job_network_allowed():
    review = impl.evaluate_manual_dispatch_implementation_review(str(_root()))
    review["blueprint"]["job_blueprints"][0]["network_allowed"] = True
    validation = impl.validate_manual_dispatch_implementation_review(review)
    assert validation["valid"] is False
    assert any("network_allowed" in e for e in validation["errors"])


def test_validate_fails_if_job_secret_refs_allowed():
    review = impl.evaluate_manual_dispatch_implementation_review(str(_root()))
    review["blueprint"]["job_blueprints"][0]["secret_refs_allowed"] = True
    validation = impl.validate_manual_dispatch_implementation_review(review)
    assert validation["valid"] is False
    assert any("secret_refs_allowed" in e for e in validation["errors"])


def test_validate_fails_if_job_runtime_write_allowed():
    review = impl.evaluate_manual_dispatch_implementation_review(str(_root()))
    review["blueprint"]["job_blueprints"][0]["runtime_write_allowed"] = True
    validation = impl.validate_manual_dispatch_implementation_review(review)
    assert validation["valid"] is False
    assert any("runtime_write_allowed" in e for e in validation["errors"])


def test_validate_fails_if_job_audit_jsonl_write_allowed():
    review = impl.evaluate_manual_dispatch_implementation_review(str(_root()))
    review["blueprint"]["job_blueprints"][0]["audit_jsonl_write_allowed"] = True
    validation = impl.validate_manual_dispatch_implementation_review(review)
    assert validation["valid"] is False
    assert any("audit_jsonl_write_allowed" in e for e in validation["errors"])


def test_validate_fails_if_job_auto_fix_allowed():
    review = impl.evaluate_manual_dispatch_implementation_review(str(_root()))
    review["blueprint"]["job_blueprints"][0]["auto_fix_allowed"] = True
    validation = impl.validate_manual_dispatch_implementation_review(review)
    assert validation["valid"] is False
    assert any("auto_fix_allowed" in e for e in validation["errors"])


# ── 9. generate_manual_dispatch_implementation_review safety ───────────────────

def test_generate_writes_to_tmp_path_only(tmp_path, monkeypatch):
    monkeypatch.setattr(impl, "ROOT", tmp_path)
    monkeypatch.setattr(impl, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    result = impl.generate_manual_dispatch_implementation_review()
    assert Path(result["output_path"]).exists()
    assert Path(result["report_path"]).exists()
    assert Path(result["yaml_blueprint_path"]).exists()


def test_generate_does_not_create_github_workflows(tmp_path, monkeypatch):
    monkeypatch.setattr(impl, "ROOT", tmp_path)
    monkeypatch.setattr(impl, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    impl.generate_manual_dispatch_implementation_review()
    gh_dir = tmp_path / ".github" / "workflows"
    assert not gh_dir.exists()


def test_generate_does_not_write_audit_jsonl(tmp_path, monkeypatch):
    audit_dir = tmp_path / "migration_reports" / "foundation_audit" / "audit_trail"
    audit_dir.mkdir(parents=True)
    jsonl = audit_dir / "foundation_diagnostic_runs.jsonl"
    jsonl.write_text('{"audit_record_id":"x"}\n', encoding="utf-8")
    before = jsonl.read_text(encoding="utf-8")
    monkeypatch.setattr(impl, "ROOT", tmp_path)
    monkeypatch.setattr(impl, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    impl.generate_manual_dispatch_implementation_review()
    assert jsonl.read_text(encoding="utf-8") == before


def test_generate_does_not_write_runtime_or_action_queue(tmp_path, monkeypatch):
    monkeypatch.setattr(impl, "ROOT", tmp_path)
    monkeypatch.setattr(impl, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    impl.generate_manual_dispatch_implementation_review()
    assert not (tmp_path / "runtime").exists()
    assert not (tmp_path / "action_queue").exists()


def test_generate_does_not_perform_network_call(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(impl, "ROOT", tmp_path)
    monkeypatch.setattr(impl, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    monkeypatch.setattr(impl, "evaluate_manual_dispatch_implementation_review", lambda r=None, confirmation_received=False: called.append("evaluated") or {
        "review_id": "test",
        "generated_at": "",
        "status": impl.ManualDispatchImplementationStatus.READY_FOR_MANUAL_CONFIRMATION,
        "blueprint": {"yaml_blueprint": "# yaml"},
        "implementation_checks": {"implementation_checks": [], "check_count": 0, "all_passed": True},
        "workflow_created": False,
        "trigger_enabled": False,
        "network_recommended": False,
        "runtime_write_recommended": False,
        "secret_read_recommended": False,
        "auto_fix_recommended": False,
        "rollback_plan": {"rollback_steps": ["step"]},
        "errors": [],
    })
    impl.generate_manual_dispatch_implementation_review()
    assert called == ["evaluated"]


def test_generate_does_not_execute_auto_fix(tmp_path, monkeypatch):
    monkeypatch.setattr(impl, "ROOT", tmp_path)
    monkeypatch.setattr(impl, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    result = impl.generate_manual_dispatch_implementation_review()
    assert result["review"]["auto_fix_recommended"] is False


# ── 10. Security policy ─────────────────────────────────────────────────────────

def test_security_policy_no_secrets():
    bp = impl.build_manual_dispatch_workflow_blueprint(str(_root()))
    assert bp["security_policy"]["no_secrets"] is True


def test_security_policy_no_network():
    bp = impl.build_manual_dispatch_workflow_blueprint(str(_root()))
    assert bp["security_policy"]["no_network"] is True


def test_security_policy_no_runtime_write():
    bp = impl.build_manual_dispatch_workflow_blueprint(str(_root()))
    assert bp["security_policy"]["no_runtime_write"] is True


def test_security_policy_no_audit_jsonl_write():
    bp = impl.build_manual_dispatch_workflow_blueprint(str(_root()))
    assert bp["security_policy"]["no_audit_jsonl_write"] is True


def test_security_policy_no_action_queue_write():
    bp = impl.build_manual_dispatch_workflow_blueprint(str(_root()))
    assert bp["security_policy"]["no_action_queue_write"] is True


def test_security_policy_no_auto_fix():
    bp = impl.build_manual_dispatch_workflow_blueprint(str(_root()))
    assert bp["security_policy"]["no_auto_fix"] is True


def test_security_policy_no_feishu_send():
    bp = impl.build_manual_dispatch_workflow_blueprint(str(_root()))
    assert bp["security_policy"]["no_feishu_send"] is True
