"""Tests for R241-16B local CI dry-run helpers.

These tests validate plan-only and monkeypatched execution paths. They do not
create workflow files, write audit JSONL/runtime/action queue files, call
network/webhooks, read secrets, or execute auto-fix.
"""

from __future__ import annotations

import importlib.util
import subprocess
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.foundation import ci_implementation_plan as impl
from app.foundation import ci_local_dryrun as dryrun


def _stage(stage_type: str) -> dict:
    specs = dryrun.load_ci_stage_specs_for_local_run()["stage_specs"]
    return next(stage for stage in specs if stage["stage_type"] == stage_type)


def _script_module():
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "ci_foundation_check.py"
    spec = importlib.util.spec_from_file_location("ci_foundation_check_test", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_load_ci_stage_specs_for_local_run_returns_core_stages():
    result = dryrun.load_ci_stage_specs_for_local_run()
    stage_types = {stage["stage_type"] for stage in result["stage_specs"]}
    assert impl.CIExecutionStageType.FAST in stage_types
    assert impl.CIExecutionStageType.SAFETY in stage_types
    assert impl.CIExecutionStageType.SLOW in stage_types
    assert impl.CIExecutionStageType.FULL in stage_types


def test_select_ci_stages_all_pr_contains_smoke_fast_safety_collect_only():
    specs = dryrun.load_ci_stage_specs_for_local_run()["stage_specs"]
    selected = dryrun.select_ci_stages(specs, "all_pr")
    assert selected["selected_stage_types"] == ["smoke", "fast", "safety", "collect_only"]


def test_select_ci_stages_all_nightly_contains_fast_safety_slow():
    specs = dryrun.load_ci_stage_specs_for_local_run()["stage_specs"]
    selected = dryrun.select_ci_stages(specs, "all_nightly")
    assert selected["selected_stage_types"] == ["fast", "safety", "slow"]


def test_select_ci_stages_fast_only_contains_fast():
    specs = dryrun.load_ci_stage_specs_for_local_run()["stage_specs"]
    selected = dryrun.select_ci_stages(specs, "fast")
    assert selected["selected_stage_types"] == ["fast"]


def test_run_ci_stage_command_execute_false_does_not_run_subprocess(monkeypatch):
    def fail_run(*args, **kwargs):
        raise AssertionError("subprocess must not run")

    monkeypatch.setattr(dryrun.subprocess, "run", fail_run)
    result = dryrun.run_ci_stage_command(_stage("fast"), execute=False)
    assert result["status"] == dryrun.LocalCIStageStatus.PENDING
    assert result["exit_code"] is None


def test_run_ci_stage_command_execute_true_uses_subprocess_without_shell(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append({"args": args, **kwargs})
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(dryrun.subprocess, "run", fake_run)
    result = dryrun.run_ci_stage_command(_stage("safety"), execute=True, timeout_seconds=10)
    assert result["status"] == dryrun.LocalCIStageStatus.PASSED
    assert calls
    assert calls[0]["shell"] is False
    assert isinstance(calls[0]["args"], list)


def test_run_ci_stage_command_rejects_unknown_command():
    result = dryrun.run_ci_stage_command(
        {
            "stage_id": "unknown",
            "stage_type": "unknown",
            "name": "Unknown",
            "command": "python -c print(1)",
        },
        execute=True,
    )
    assert result["status"] == dryrun.LocalCIStageStatus.BLOCKED_BY_POLICY
    assert "unknown_stage_command_blocked" in result["errors"]


def test_evaluate_stage_threshold_exit_code_failed():
    stage = _stage("fast")
    result = dryrun.evaluate_stage_threshold(
        {**dryrun.run_ci_stage_command(stage, execute=False), "exit_code": 1, "status": "failed"},
        impl.build_ci_threshold_policy(),
    )
    assert result["status"] == dryrun.LocalCIStageStatus.FAILED
    assert result["threshold_status"] == "failed"


def test_evaluate_stage_threshold_runtime_warning():
    stage = _stage("slow")
    pending = dryrun.run_ci_stage_command(stage, execute=False)
    pending["exit_code"] = 0
    pending["runtime_seconds"] = 61
    pending["status"] = dryrun.LocalCIStageStatus.PASSED
    result = dryrun.evaluate_stage_threshold(pending, impl.build_ci_threshold_policy())
    assert result["status"] == dryrun.LocalCIStageStatus.WARNING
    assert result["threshold_status"] == "threshold_warning"


def test_run_local_ci_dryrun_execute_false_does_not_run_pytest(monkeypatch):
    def fail_run(*args, **kwargs):
        raise AssertionError("pytest must not run")

    monkeypatch.setattr(dryrun.subprocess, "run", fail_run)
    result = dryrun.run_local_ci_dryrun(selection="all_pr", execute=False)
    assert result["mode"] == dryrun.LocalCIRunMode.PLAN_ONLY
    assert all(stage["exit_code"] is None for stage in result["stage_results"] if stage["selected"])


def test_run_local_ci_dryrun_all_pr_selects_correct_stages():
    result = dryrun.run_local_ci_dryrun(selection="all_pr", execute=False)
    assert result["selected_stages"] == ["smoke", "fast", "safety", "collect_only"]


def test_format_local_ci_result_json_returns_dict():
    result = dryrun.run_local_ci_dryrun(selection="fast", execute=False)
    assert isinstance(dryrun.format_local_ci_result(result, "json"), dict)


def test_format_local_ci_result_markdown_contains_no_auto_fix_notice():
    result = dryrun.run_local_ci_dryrun(selection="fast", execute=False)
    text = dryrun.format_local_ci_result(result, "markdown")
    assert isinstance(text, str)
    assert "no auto-fix" in text


def test_format_local_ci_result_text_contains_no_network_notice():
    result = dryrun.run_local_ci_dryrun(selection="fast", execute=False)
    text = dryrun.format_local_ci_result(result, "text")
    assert isinstance(text, str)
    assert "no network" in text


def test_generate_local_ci_dryrun_sample_only_writes_tmp_path(tmp_path: Path):
    output = tmp_path / "R241-16B_LOCAL_CI_DRYRUN_SAMPLE.json"
    result = dryrun.generate_local_ci_dryrun_sample(str(output))
    assert Path(result["output_path"]) == output
    assert output.exists()
    assert not list(tmp_path.rglob("*.jsonl"))


def test_script_plan_only_json_exit_0(capsys):
    script = _script_module()
    assert script.main(["--selection", "all_pr", "--format", "json"]) == 0
    assert '"selected_stages"' in capsys.readouterr().out


def test_script_plan_only_markdown_exit_0(capsys):
    script = _script_module()
    assert script.main(["--selection", "all_nightly", "--format", "markdown"]) == 0
    assert "Local CI Dry-run Result" in capsys.readouterr().out


@pytest.mark.parametrize("flag", ["--send", "--webhook", "--auto-fix"])
def test_script_rejects_forbidden_flags(flag):
    script = _script_module()
    with pytest.raises(SystemExit):
        script.main([flag])


def test_no_github_workflow_created_by_sample(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(dryrun, "DEFAULT_SAMPLE_PATH", tmp_path / "R241-16B_LOCAL_CI_DRYRUN_SAMPLE.json")
    dryrun.generate_local_ci_dryrun_sample()
    assert not (tmp_path / ".github" / "workflows").exists()


def test_no_audit_jsonl_written(tmp_path: Path):
    dryrun.generate_local_ci_dryrun_sample(str(tmp_path / "R241-16B_LOCAL_CI_DRYRUN_SAMPLE.json"))
    assert not list(tmp_path.rglob("*.jsonl"))


def test_no_runtime_or_action_queue_written(tmp_path: Path):
    dryrun.generate_local_ci_dryrun_sample(str(tmp_path / "R241-16B_LOCAL_CI_DRYRUN_SAMPLE.json"))
    written_names = {path.name for path in tmp_path.rglob("*") if path.is_file()}
    assert "action_queue.json" not in written_names
    assert "governance_state.json" not in written_names
    assert "experiment_queue.json" not in written_names


def test_no_network_or_webhook_call(monkeypatch):
    def fail_network(*args, **kwargs):
        raise AssertionError("network/webhook call is forbidden")

    monkeypatch.setattr(urllib.request, "urlopen", fail_network)
    result = dryrun.run_local_ci_dryrun(selection="fast", execute=False)
    assert result["blocked_actions_verified"]["no_network_call"] is True
    assert result["blocked_actions_verified"]["no_webhook_call"] is True


def test_no_secret_read(monkeypatch):
    def fail_getenv(*args, **kwargs):
        raise AssertionError("secret env read is forbidden")

    monkeypatch.setattr("os.getenv", fail_getenv)
    result = dryrun.run_local_ci_dryrun(selection="fast", execute=False)
    assert result["blocked_actions_verified"]["no_secret_read"] is True


def test_no_auto_fix():
    result = dryrun.run_local_ci_dryrun(selection="fast", execute=False)
    assert result["blocked_actions_verified"]["no_auto_fix"] is True


def test_execute_true_monkeypatch_does_not_use_shell(monkeypatch):
    shell_values = []

    def fake_run(args, **kwargs):
        shell_values.append(kwargs.get("shell"))
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(dryrun.subprocess, "run", fake_run)
    result = dryrun.run_local_ci_dryrun(selection="safety", execute=True)
    assert result["overall_status"] == dryrun.LocalCIStageStatus.PASSED
    assert shell_values == [False]
