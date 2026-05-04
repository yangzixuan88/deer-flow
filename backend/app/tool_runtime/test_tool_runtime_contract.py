import json
import sys

sys.path.insert(0, ".")


def test_read_file_level_0():
    from app.tool_runtime.tool_runtime_contract import classify_tool_operation

    result = classify_tool_operation("read_file", "README.md")
    assert result["risk_level"] == "level_0_free_readonly"


def test_edit_code_level_1():
    from app.tool_runtime.tool_runtime_contract import classify_tool_operation

    result = classify_tool_operation("edit_code", "backend/app/foo.py")
    assert result["risk_level"] == "level_1_standard_auto"


def test_package_json_modify_config_level_2():
    from app.tool_runtime.tool_runtime_contract import classify_tool_operation

    result = classify_tool_operation("modify_config", "package.json")
    assert result["risk_level"] == "level_2_protected_auto"
    assert "critical_config_path" in result["reasons"]


def test_delete_file_important_level_3_archive_warning():
    from app.tool_runtime.tool_runtime_contract import decide_protected_operation

    result = decide_protected_operation("delete_file", "important.md")
    assert result["risk_level"] == "level_3_confirm_or_archive"
    assert result["should_archive_instead_of_delete"] is True
    assert "delete_should_archive" in result["warnings"]


def test_prompt_replace_without_rollback_warning():
    from app.tool_runtime.tool_runtime_contract import create_tool_execution_event, validate_tool_event_policy

    event = create_tool_execution_event("prompt", "prompt_replace", "test", {"tool_type": "file_system"})
    validation = validate_tool_event_policy(event)
    assert event["risk_level"] == "level_3_confirm_or_archive"
    assert "prompt_replace_missing_rollback" in validation["warnings"]


def test_memory_cleanup_quarantine_warning():
    from app.tool_runtime.tool_runtime_contract import create_tool_execution_event, validate_tool_event_policy

    event = create_tool_execution_event("memory", "memory_cleanup", "test", {"tool_type": "python"})
    validation = validate_tool_event_policy(event)
    assert "memory_cleanup_requires_quarantine" in validation["warnings"]
    assert "quarantine_or_observation_before_cleanup" in validation["required_followups"]


def test_asset_elimination_core_forbidden_confirmation_warning():
    from app.tool_runtime.tool_runtime_contract import create_tool_execution_event, validate_tool_event_policy

    event = create_tool_execution_event(
        "asset",
        "asset_elimination",
        "test",
        {"tool_type": "python", "asset_tier": "Core"},
    )
    validation = validate_tool_event_policy(event)
    assert event["risk_level"] == "level_3_confirm_or_archive"
    assert "asset_core_elimination_forbidden" in validation["warnings"]


def test_create_tool_policy_shell_requires_root_guard():
    from app.tool_runtime.tool_runtime_contract import create_tool_policy

    policy = create_tool_policy("shell", "shell", "test")
    assert policy["requires_root_guard"] is True
    assert policy["can_execute_shell"] is True


def test_create_tool_policy_search_readonly_no_backup():
    from app.tool_runtime.tool_runtime_contract import create_tool_policy

    policy = create_tool_policy("search", "search", "test", {"readonly": True})
    assert policy["default_risk_level"] == "level_0_free_readonly"
    assert policy["audit_required"] is False
    assert policy["requires_backup_for"] == ["level_2_protected_auto", "level_3_confirm_or_archive"]


def test_create_tool_execution_event_does_not_execute_tool():
    from app.tool_runtime.tool_runtime_contract import create_tool_execution_event

    event = create_tool_execution_event("shell", "shell_command", "test", {"tool_type": "shell"})
    assert event["status"] == "planned"
    assert event["success"] is None
    assert event["tool_execution_id"].startswith("toolexec_")


def test_complete_tool_execution_event_success_completed():
    from app.tool_runtime.tool_runtime_contract import complete_tool_execution_event, create_tool_execution_event

    event = create_tool_execution_event("test", "run_test", "test", {"tool_type": "python"})
    updated = complete_tool_execution_event(event, True, artifact_refs=["pytest.log"], modified_files=[])
    assert updated["status"] == "completed"
    assert updated["success"] is True
    assert "pytest.log" in updated["artifact_refs"]


def test_complete_tool_execution_event_failure_failed():
    from app.tool_runtime.tool_runtime_contract import complete_tool_execution_event, create_tool_execution_event

    event = create_tool_execution_event("test", "run_test", "test", {"tool_type": "python"})
    updated = complete_tool_execution_event(event, False)
    assert updated["status"] == "failed"
    assert updated["success"] is False


def test_validate_level_2_missing_backup_warning():
    from app.tool_runtime.tool_runtime_contract import create_tool_execution_event, validate_tool_event_policy

    event = create_tool_execution_event("config", "modify_config", "test", {"tool_type": "file_system", "target_path": "package.json"})
    validation = validate_tool_event_policy(event)
    assert "level_2_missing_backup" in validation["warnings"]
    assert "level_2_missing_rollback" in validation["warnings"]


def test_validate_root_guard_missing_warning():
    from app.tool_runtime.tool_runtime_contract import create_tool_execution_event, validate_tool_event_policy

    event = create_tool_execution_event("edit", "edit_code", "test", {"tool_type": "file_system"})
    validation = validate_tool_event_policy(event)
    assert "root_guard_required_but_missing" in validation["warnings"]


def test_summarize_tool_events_counts_risk_levels():
    from app.tool_runtime.tool_runtime_contract import create_tool_execution_event, summarize_tool_events

    events = [
        create_tool_execution_event("read", "read_file", "test", {"tool_type": "file_system"}),
        create_tool_execution_event("edit", "edit_code", "test", {"tool_type": "file_system"}),
        create_tool_execution_event("config", "modify_config", "test", {"tool_type": "file_system", "target_path": "package.json"}),
    ]
    summary = summarize_tool_events(events)
    assert summary["total"] == 3
    assert summary["by_risk_level"]["level_0_free_readonly"] == 1
    assert summary["by_risk_level"]["level_1_standard_auto"] == 1
    assert summary["by_risk_level"]["level_2_protected_auto"] == 1
    assert summary["high_risk_count"] == 1


def test_generate_tool_runtime_sample_writes_only_tmp_path(tmp_path):
    from app.tool_runtime.tool_runtime_contract import generate_tool_runtime_sample

    output = tmp_path / "tool_sample.json"
    result = generate_tool_runtime_sample(str(output))
    assert result["output_path"] == str(output)
    assert output.exists()
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["summary"]["total"] == 8
    assert sorted(path.name for path in tmp_path.iterdir()) == ["tool_sample.json"]


def test_metadata_mode_invocation_id_preserved():
    from app.tool_runtime.tool_runtime_contract import create_tool_execution_event

    event = create_tool_execution_event(
        "claude",
        "claude_code_call",
        "test",
        {"tool_type": "claude_code", "mode_invocation_id": "modeinv_123"},
    )
    assert event["mode_invocation_id"] == "modeinv_123"


def test_unknown_operation_returns_unknown_warning():
    from app.tool_runtime.tool_runtime_contract import classify_tool_operation

    result = classify_tool_operation("nonexistent_op")
    assert result["operation_type"] == "unknown"
    assert result["risk_level"] == "unknown"
    assert "unknown_operation_type:nonexistent_op" in result["warnings"]
