"""Tests for R241-16D PR blocking enablement review.

These tests are review-only. They do not create workflows, enable triggers,
write audit JSONL/runtime/action queue files, call network/webhooks, read
secrets, or execute auto-fix.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

from app.foundation import ci_enablement_review as review


def test_discover_existing_workflows_returns_list(tmp_path: Path):
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "test.yml").write_text("name: test\n", encoding="utf-8")
    result = review.discover_existing_workflows(str(tmp_path))
    assert result["workflow_count"] == 1
    assert result["workflows"]


def test_discover_existing_workflows_does_not_create_directory(tmp_path: Path):
    result = review.discover_existing_workflows(str(tmp_path))
    assert result["workflow_count"] == 0
    assert not (tmp_path / ".github" / "workflows").exists()


def test_analyze_existing_workflow_compatibility_identifies_pull_request(tmp_path: Path):
    path = tmp_path / "ci.yml"
    path.write_text("on:\n  pull_request:\n", encoding="utf-8")
    result = review.analyze_existing_workflow_compatibility(str(path))
    assert result["trigger_summary"]["pull_request"] is True


def test_analyze_existing_workflow_compatibility_identifies_pytest(tmp_path: Path):
    path = tmp_path / "ci.yml"
    path.write_text("jobs:\n  test:\n    steps:\n      - run: pytest backend/app/foundation\n", encoding="utf-8")
    result = review.analyze_existing_workflow_compatibility(str(path))
    assert result["runs_pytest"] is True


def test_analyze_existing_workflow_compatibility_unparsed_uses_warning(tmp_path: Path):
    path = tmp_path / "ci.yml"
    path.write_text("not: [strictly yaml maybe\n", encoding="utf-8")
    result = review.analyze_existing_workflow_compatibility(str(path))
    assert result["parsed"] is True
    assert "yaml_text_heuristic_analysis_used" in result["warnings"]


def test_build_checks_contains_disabled_draft_valid():
    checks = review.build_pr_blocking_enablement_checks()["checks"]
    assert any(check["check_type"] == "disabled_workflow_draft_valid" for check in checks)


def test_build_checks_contains_security_checks():
    checks = review.build_pr_blocking_enablement_checks()["checks"]
    types = {check["check_type"] for check in checks}
    assert "no_secret_refs" in types
    assert "no_network_or_webhook" in types
    assert "no_runtime_write" in types


def test_build_checks_contains_path_compatibility():
    checks = review.build_pr_blocking_enablement_checks()["checks"]
    assert any(check["check_type"] == "path_compatibility_report_only_or_accepted" for check in checks)


def test_rollback_plan_contains_remove_pull_request_trigger():
    rollback = review.build_enablement_rollback_plan()
    assert any("Remove pull_request trigger" in step for step in rollback["rollback_steps"])


def test_rollback_plan_contains_revert_workflow_file():
    rollback = review.build_enablement_rollback_plan()
    assert any("Revert workflow file" in step for step in rollback["rollback_steps"])


def test_manual_confirmation_contains_phrase():
    confirmation = review.build_manual_confirmation_requirements()
    assert confirmation["confirmation_phrase"] == "CONFIRM_ENABLE_FOUNDATION_FAST_SAFETY_CI"


def test_enablement_options_contains_a_to_d():
    options = review.build_enablement_options()["options"]
    ids = {option["option_id"] for option in options}
    assert {"option_a", "option_b", "option_c", "option_d"}.issubset(ids)


def test_recommended_option_non_empty():
    result = review.build_enablement_options()
    assert result["recommended_option"]


def test_evaluate_pr_blocking_readiness_returns_review():
    result = review.evaluate_pr_blocking_readiness()
    assert result["review_id"] == "R241-16D_pr_blocking_enablement_review"
    assert "existing_workflows" in result


def test_validate_pr_blocking_enablement_review_valid_true():
    result = review.evaluate_pr_blocking_readiness()
    validation = review.validate_pr_blocking_enablement_review(result)
    assert validation["valid"] is True


def test_validate_rejects_network_recommended():
    result = review.evaluate_pr_blocking_readiness()
    result["network_recommended"] = True
    validation = review.validate_pr_blocking_enablement_review(result)
    assert validation["valid"] is False
    assert "network_recommended_not_allowed" in validation["errors"]


def test_validate_rejects_runtime_write_recommended():
    result = review.evaluate_pr_blocking_readiness()
    result["runtime_write_recommended"] = True
    validation = review.validate_pr_blocking_enablement_review(result)
    assert validation["valid"] is False
    assert "runtime_write_recommended_not_allowed" in validation["errors"]


def test_validate_rejects_missing_rollback_plan():
    result = review.evaluate_pr_blocking_readiness()
    result["rollback_plan"] = {}
    validation = review.validate_pr_blocking_enablement_review(result)
    assert validation["valid"] is False
    assert "rollback_plan_missing" in validation["errors"]


def test_validate_rejects_missing_manual_confirmation():
    result = review.evaluate_pr_blocking_readiness()
    result["manual_confirmation_requirements"] = {}
    validation = review.validate_pr_blocking_enablement_review(result)
    assert validation["valid"] is False
    assert "manual_confirmation_missing" in validation["errors"]


def test_generate_pr_blocking_enablement_review_only_writes_tmp_path(tmp_path: Path):
    output = tmp_path / "R241-16D_PR_BLOCKING_ENABLEMENT_REVIEW.json"
    result = review.generate_pr_blocking_enablement_review(str(output))
    assert Path(result["output_path"]) == output
    assert output.exists()
    assert (tmp_path / "R241-16D_PR_BLOCKING_ENABLEMENT_REVIEW.md").exists()
    assert not (tmp_path / ".github" / "workflows").exists()


def test_no_workflow_written(tmp_path: Path):
    review.generate_pr_blocking_enablement_review(str(tmp_path / "R241-16D_PR_BLOCKING_ENABLEMENT_REVIEW.json"))
    assert not list(tmp_path.rglob(".github/workflows/*.yml"))
    assert not list(tmp_path.rglob(".github/workflows/*.yaml"))


def test_no_audit_jsonl_written(tmp_path: Path):
    review.generate_pr_blocking_enablement_review(str(tmp_path / "R241-16D_PR_BLOCKING_ENABLEMENT_REVIEW.json"))
    assert not list(tmp_path.rglob("*.jsonl"))


def test_no_runtime_or_action_queue_written(tmp_path: Path):
    review.generate_pr_blocking_enablement_review(str(tmp_path / "R241-16D_PR_BLOCKING_ENABLEMENT_REVIEW.json"))
    written_names = {path.name for path in tmp_path.rglob("*") if path.is_file()}
    assert "action_queue.json" not in written_names
    assert "governance_state.json" not in written_names
    assert "experiment_queue.json" not in written_names


def test_no_network_or_webhook_call(monkeypatch):
    def fail_network(*args, **kwargs):
        raise AssertionError("network/webhook call is forbidden")

    monkeypatch.setattr(urllib.request, "urlopen", fail_network)
    result = review.evaluate_pr_blocking_readiness()
    assert result["network_recommended"] is False


def test_no_auto_fix():
    result = review.evaluate_pr_blocking_readiness()
    assert result["auto_fix_recommended"] is False
