"""Tests for R241-16C disabled workflow draft design.

These tests only validate report-directory workflow draft artifacts. They do
not create active workflow files, enable triggers, call network/webhooks, read
secrets, write runtime/audit JSONL/action queue files, or execute auto-fix.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

from app.foundation import ci_workflow_draft as draft


def test_build_workflow_trigger_policy_disables_pull_request():
    policy = draft.build_workflow_trigger_policy()
    assert policy["pull_request_enabled"] is False


def test_build_workflow_trigger_policy_disables_push():
    policy = draft.build_workflow_trigger_policy()
    assert policy["push_enabled"] is False


def test_build_workflow_trigger_policy_disables_schedule():
    policy = draft.build_workflow_trigger_policy()
    assert policy["schedule_enabled"] is False


def test_build_workflow_trigger_policy_auto_triggers_false():
    policy = draft.build_workflow_trigger_policy()
    assert policy["auto_triggers_enabled"] is False


def test_build_workflow_job_specs_contains_required_jobs():
    jobs = draft.build_workflow_job_specs()["jobs"]
    job_types = {job["job_type"] for job in jobs}
    assert {
        "smoke",
        "fast",
        "safety",
        "slow",
        "full",
        "collect_only",
        "artifact_collection",
    }.issubset(job_types)


def test_every_job_network_allowed_false():
    jobs = draft.build_workflow_job_specs()["jobs"]
    assert all(job["network_allowed"] is False for job in jobs)


def test_every_job_runtime_write_allowed_false():
    jobs = draft.build_workflow_job_specs()["jobs"]
    assert all(job["runtime_write_allowed"] is False for job in jobs)


def test_every_job_auto_fix_allowed_false():
    jobs = draft.build_workflow_job_specs()["jobs"]
    assert all(job["auto_fix_allowed"] is False for job in jobs)


def test_every_job_secret_refs_allowed_false():
    jobs = draft.build_workflow_job_specs()["jobs"]
    assert all(job["secret_refs_allowed"] is False for job in jobs)


def test_artifact_policy_collects_primary_report_path():
    policy = draft.build_workflow_artifact_policy()
    assert "migration_reports/foundation_audit/*.json" in policy["include_paths"]
    assert "migration_reports/foundation_audit/*.md" in policy["include_paths"]


def test_artifact_policy_collects_secondary_report_path_temporarily():
    policy = draft.build_workflow_artifact_policy()
    assert "backend/migration_reports/foundation_audit/*.json" in policy["include_paths"]
    assert policy["collect_secondary_report_path_temporarily"] is True


def test_artifact_policy_excludes_audit_trail_jsonl():
    policy = draft.build_workflow_artifact_policy()
    assert "**/audit_trail/*.jsonl" in policy["exclude_patterns"]


def test_artifact_policy_excludes_runtime_and_action_queue():
    policy = draft.build_workflow_artifact_policy()
    assert "**/runtime/**" in policy["exclude_patterns"]
    assert "**/action_queue/**" in policy["exclude_patterns"]


def test_artifact_policy_excludes_secret_token_webhook_patterns():
    policy = draft.build_workflow_artifact_policy()
    excludes = " ".join(policy["exclude_patterns"])
    assert "secret" in excludes
    assert "token" in excludes
    assert "webhook" in excludes


def test_render_disabled_workflow_yaml_draft_contains_disabled_comment():
    spec = draft.build_disabled_workflow_draft_spec()
    yaml_text = draft.render_disabled_workflow_yaml_draft(spec)["yaml_text"]
    assert "DISABLED DRAFT" in yaml_text
    assert "DO NOT ENABLE WITHOUT USER CONFIRMATION" in yaml_text


def test_yaml_draft_does_not_contain_pull_request_trigger():
    yaml_text = draft.build_disabled_workflow_draft_spec()["yaml_draft"]
    assert "pull_request:" not in yaml_text


def test_yaml_draft_does_not_contain_push_trigger():
    yaml_text = draft.build_disabled_workflow_draft_spec()["yaml_draft"]
    assert "push:" not in yaml_text


def test_yaml_draft_does_not_contain_schedule_trigger():
    yaml_text = draft.build_disabled_workflow_draft_spec()["yaml_draft"]
    assert "schedule:" not in yaml_text


def test_yaml_draft_does_not_contain_secrets_ref():
    yaml_text = draft.build_disabled_workflow_draft_spec()["yaml_draft"]
    assert "secrets." not in yaml_text


def test_yaml_draft_does_not_contain_webhook_curl_or_network_call():
    yaml_text = draft.build_disabled_workflow_draft_spec()["yaml_draft"].lower()
    assert "webhook" not in yaml_text
    assert "curl" not in yaml_text
    assert "invoke-webrequest" not in yaml_text


def test_validate_disabled_workflow_draft_valid_true():
    spec = draft.build_disabled_workflow_draft_spec()
    validation = draft.validate_disabled_workflow_draft(spec)
    assert validation["valid"] is True


def test_validate_disabled_workflow_draft_rejects_pull_request_enabled():
    spec = draft.build_disabled_workflow_draft_spec()
    spec["pull_request_enabled"] = True
    validation = draft.validate_disabled_workflow_draft(spec)
    assert validation["valid"] is False
    assert "validation_failed:no_pr_trigger" in validation["errors"]


def test_validate_disabled_workflow_draft_rejects_secret_refs():
    spec = draft.build_disabled_workflow_draft_spec()
    spec["jobs"][0]["secret_refs_allowed"] = True
    validation = draft.validate_disabled_workflow_draft(spec)
    assert validation["valid"] is False
    assert "validation_failed:no_secret_refs" in validation["errors"]


def test_validate_disabled_workflow_draft_rejects_network_allowed():
    spec = draft.build_disabled_workflow_draft_spec()
    spec["jobs"][0]["network_allowed"] = True
    validation = draft.validate_disabled_workflow_draft(spec)
    assert validation["valid"] is False
    assert "validation_failed:no_network" in validation["errors"]


def test_validate_disabled_workflow_draft_rejects_auto_fix_allowed():
    spec = draft.build_disabled_workflow_draft_spec()
    spec["jobs"][0]["auto_fix_allowed"] = True
    validation = draft.validate_disabled_workflow_draft(spec)
    assert validation["valid"] is False
    assert "validation_failed:no_auto_fix" in validation["errors"]


def test_generate_disabled_workflow_draft_plan_only_writes_tmp_path(tmp_path: Path):
    output = tmp_path / "R241-16C_DISABLED_WORKFLOW_DRAFT_PLAN.json"
    result = draft.generate_disabled_workflow_draft_plan(str(output))
    assert Path(result["output_path"]) == output
    assert output.exists()
    assert (tmp_path / "R241-16C_DISABLED_WORKFLOW_DRAFT_REPORT.md").exists()
    assert (tmp_path / "R241-16C_FOUNDATION_CHECK_WORKFLOW_DRAFT.yml.txt").exists()
    assert not (tmp_path / ".github" / "workflows").exists()


def test_no_github_workflow_written(tmp_path: Path):
    draft.generate_disabled_workflow_draft_plan(str(tmp_path / "R241-16C_DISABLED_WORKFLOW_DRAFT_PLAN.json"))
    assert not list(tmp_path.rglob(".github/workflows/*.yml"))
    assert not list(tmp_path.rglob(".github/workflows/*.yaml"))


def test_no_audit_jsonl_written(tmp_path: Path):
    draft.generate_disabled_workflow_draft_plan(str(tmp_path / "R241-16C_DISABLED_WORKFLOW_DRAFT_PLAN.json"))
    assert not list(tmp_path.rglob("*.jsonl"))


def test_no_runtime_or_action_queue_written(tmp_path: Path):
    draft.generate_disabled_workflow_draft_plan(str(tmp_path / "R241-16C_DISABLED_WORKFLOW_DRAFT_PLAN.json"))
    written_names = {path.name for path in tmp_path.rglob("*") if path.is_file()}
    assert "action_queue.json" not in written_names
    assert "governance_state.json" not in written_names
    assert "experiment_queue.json" not in written_names


def test_no_network_or_webhook_call(monkeypatch):
    def fail_network(*args, **kwargs):
        raise AssertionError("network/webhook call is forbidden")

    monkeypatch.setattr(urllib.request, "urlopen", fail_network)
    spec = draft.build_disabled_workflow_draft_spec()
    validation = draft.validate_disabled_workflow_draft(spec)
    assert validation["valid"] is True


def test_no_auto_fix():
    spec = draft.build_disabled_workflow_draft_spec()
    assert all(job["auto_fix_allowed"] is False for job in spec["jobs"])
