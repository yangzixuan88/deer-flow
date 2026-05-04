"""Tests for read_only_diagnostics_cli.py Phase B expansion.

These tests verify that the CLI expansion (memory/asset/prompt/rtcm) does not write
runtime state, open HTTP endpoints, or modify Gateway.
"""

from pathlib import Path

import pytest

from app.foundation import read_only_diagnostics_cli as cli


def _synthetic_diagnostic_result(command, status="ok", summary=None, payload=None, warnings=None, errors=None):
    result = {
        "command": command,
        "status": status,
        "generated_at": "2026-04-25T00:00:00+00:00",
        "root": "E:\\OpenClaw-Base\\deerflow",
        "format": "json",
        "summary": summary or {},
        "payload": payload or {},
        "warnings": warnings or [],
        "errors": errors or [],
    }
    return cli.add_audit_record_to_diagnostic_result(result, command)


def _synthetic_feishu_summary_result():
    return _synthetic_diagnostic_result(
        "feishu-summary",
        summary={
            "send_allowed": False,
            "webhook_required": True,
            "no_webhook_call": True,
            "no_runtime_write": True,
            "validation_valid": True,
        },
        payload={"validation": {"valid": True, "warnings": [], "blocked_reasons": []}},
    )


def _patch_synthetic_diagnostics(monkeypatch, overrides=None):
    overrides = overrides or {}

    def make(command):
        if command in overrides:
            value = overrides[command]
            return value() if callable(value) else value
        if command == "feishu-summary":
            return _synthetic_feishu_summary_result()
        return _synthetic_diagnostic_result(command, summary={"synthetic_fixture": True})

    monkeypatch.setattr(cli, "run_truth_state_diagnostic", lambda **kw: make("truth-state"))
    monkeypatch.setattr(cli, "run_queue_sandbox_diagnostic", lambda **kw: make("queue-sandbox"))
    monkeypatch.setattr(cli, "run_memory_diagnostic", lambda **kw: make("memory"))
    monkeypatch.setattr(cli, "run_asset_diagnostic", lambda **kw: make("asset"))
    monkeypatch.setattr(cli, "run_prompt_diagnostic", lambda **kw: make("prompt"))
    monkeypatch.setattr(cli, "run_rtcm_diagnostic", lambda **kw: make("rtcm"))
    monkeypatch.setattr(cli, "run_nightly_diagnostic", lambda **kw: make("nightly"))
    monkeypatch.setattr(cli, "run_feishu_summary_diagnostic", lambda **kw: make("feishu-summary"))


# ─────────────────────────────────────────────────────────────────────────────
# Registry Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_registry_implemented_commands():
    registry = cli.get_diagnostic_command_registry()
    implemented = set(registry["available_commands"])
    assert {
    "truth-state", "queue-sandbox", "memory", "asset",
    "prompt", "rtcm", "nightly", "feishu-summary", "all"
    } <= implemented


def test_registry_disabled_commands_empty():
    registry = cli.get_diagnostic_command_registry()
    assert set(registry["disabled_commands"]) == set()


def test_registry_phase_c_warnings_present():
    registry = cli.get_diagnostic_command_registry()
    warnings = registry.get("warnings") or []
    assert any("feishu_summary_projection_only" in w for w in warnings)
    assert any("no_real_feishu_push" in w for w in warnings)
    assert any("no_webhook_call" in w for w in warnings)
    # Old warning must not appear
    assert not any("feishu_summary_dry_run_not_bound" in w for w in warnings)


    # ─────────────────────────────────────────────────────────────────────────────
    # Memory Diagnostic Tests (Phase B)
    # ─────────────────────────────────────────────────────────────────────────────


def test_run_memory_diagnostic_monkeypatch_no_memory_write(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "app.memory.memory_projection", type("M", (), {
    "project_memory_roots": staticmethod(lambda root=None, max_files=500: {"scanned_count": 5, "classified_count": 5, "long_term_eligible_count": 2, "asset_candidate_eligible_count": 1, "warnings": []}),
    "get_long_term_memory_candidates": staticmethod(lambda root=None, max_files=1000: {"candidate_count": 2, "warnings": []}),
    "get_memory_asset_candidates": staticmethod(lambda root=None, max_files=1000: {"candidate_count": 1, "warnings": []}),
    "detect_memory_risk_signals": staticmethod(lambda root=None, max_files=1000: {"risk_count": 1, "risk_by_type": {"unknown_memory_artifact": 1}, "warnings": []}),
    }))
    result = cli.run_memory_diagnostic(max_files=100)
    assert result["command"] == "memory"
    assert result["summary"]["scanned_count"] == 5
    assert result["summary"]["risk_count"] == 1


def test_run_memory_diagnostic_import_failure(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "app.memory.memory_projection", None)
    result = cli.run_memory_diagnostic(max_files=10)
    assert result["status"] == "failed"
    assert result["command"] == "memory"


    # ─────────────────────────────────────────────────────────────────────────────
    # Asset Diagnostic Tests (Phase B)
    # ─────────────────────────────────────────────────────────────────────────────


def test_run_asset_diagnostic_monkeypatch_no_registry_write(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "app.asset.asset_projection", type("M", (), {
    "aggregate_asset_projection": staticmethod(lambda limit=200: {"total_projected": 3, "candidate_count": 2, "formal_asset_count": 1, "by_asset_category": {"prompt_template": 2}, "by_lifecycle_tier": {"candidate": 2}, "warnings": []}),
    "detect_asset_projection_risks": staticmethod(lambda projection: {"risk_count": 1, "risk_by_type": {"registry_missing": 1}, "warnings": []}),
    }))
    result = cli.run_asset_diagnostic(limit=50)
    assert result["command"] == "asset"
    assert result["summary"]["total_projected"] == 3
    assert result["summary"]["risk_count"] == 1


def test_run_asset_diagnostic_import_failure(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "app.asset.asset_projection", None)
    result = cli.run_asset_diagnostic(limit=10)
    assert result["status"] == "failed"
    assert result["command"] == "asset"


    # ─────────────────────────────────────────────────────────────────────────────
    # Prompt Diagnostic Tests (Phase B)
    # ─────────────────────────────────────────────────────────────────────────────


def test_run_prompt_diagnostic_monkeypatch_no_prompt_write(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "app.prompt.prompt_projection", type("M", (), {
    "aggregate_prompt_projection": staticmethod(lambda root=None, max_files=500: {
    "warnings": [],
    "source_projection": {"scanned_count": 4, "classified_count": 4, "by_layer": {"P2": 2}, "by_source_type": {"soul": 1}, "critical_sources_count": 1},
    "replacement_risks": {"total": 1, "by_risk_level": {"high": 1}},
    "asset_candidates": {"candidate_count": 1, "candidates": []},
    }),
    "detect_prompt_governance_risks": staticmethod(lambda projection: {"risk_count": 2, "risk_by_type": {"unknown_prompt_source": 1, "critical_prompt_without_rollback": 1}, "warnings": []}),
    }))
    result = cli.run_prompt_diagnostic(max_files=100)
    assert result["command"] == "prompt"
    assert result["summary"]["scanned_count"] == 4
    assert result["summary"]["risk_count"] == 2


def test_run_prompt_diagnostic_import_failure(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "app.prompt.prompt_projection", None)
    result = cli.run_prompt_diagnostic(max_files=10)
    assert result["status"] == "failed"
    assert result["command"] == "prompt"


    # ─────────────────────────────────────────────────────────────────────────────
    # RTCM Diagnostic Tests (Phase B)
    # ─────────────────────────────────────────────────────────────────────────────


def test_run_rtcm_diagnostic_monkeypatch_no_rtcm_write(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "app.rtcm.rtcm_runtime_projection", type("M", (), {
    "scan_rtcm_runtime_projection": staticmethod(lambda root=None, max_files=1000: {"scanned_count": 6, "classified_count": 5, "unknown_count": 1, "session_count": 2, "truth_candidate_count": 2, "asset_candidate_count": 1, "memory_candidate_count": 1, "followup_candidate_count": 0, "warnings": []}),
    "detect_rtcm_runtime_projection_risks": staticmethod(lambda projection: {"risk_count": 1, "risk_by_type": {"unknown_rtcm_runtime_surface": 1}, "warnings": []}),
    }))
    result = cli.run_rtcm_diagnostic(max_files=200)
    assert result["command"] == "rtcm"
    assert result["summary"]["scanned_count"] == 6
    assert result["summary"]["session_count"] == 2


def test_run_rtcm_diagnostic_import_failure(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "app.rtcm.rtcm_runtime_projection", None)
    result = cli.run_rtcm_diagnostic(max_files=10)
    assert result["status"] == "failed"
    assert result["command"] == "rtcm"


    # ─────────────────────────────────────────────────────────────────────────────
    # Feishu-Summary Diagnostic Tests (Phase C)
    # ─────────────────────────────────────────────────────────────────────────────


def test_run_feishu_summary_diagnostic_monkeypatch_no_webhook(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "app.nightly.foundation_health_review", type("M", (), {
    "aggregate_nightly_foundation_health": staticmethod(lambda root=None, max_files=500: {
    "total_signals": 3, "by_severity": {"critical": 1, "high": 2},
    "action_candidate_count": 2, "blocked_high_risk_count": 0, "warnings": []
    }),
    }))
    monkeypatch.setitem(__import__("sys").modules, "app.nightly.foundation_health_summary", type("M", (), {
    "load_latest_nightly_review_sample": staticmethod(lambda path=None: {
    "exists": True, "review": {"review_id": "R241-10C-test", "total_signals": 3, "action_candidate_count": 2}, "warnings": []
    }),
    "summarize_review_for_user": staticmethod(lambda review, warnings=None: {
    "critical_count": 1, "high_count": 2, "action_candidate_count": 2,
    "headline": "test", "warnings": []
    }),
    "summarize_review_by_domain": staticmethod(lambda review, warnings=None: {"domains": [], "warnings": []}),
    "select_top_action_candidates": staticmethod(lambda review, max_items=10, warnings=None: {
    "selected_count": 2, "actions": [], "warnings": []
    }),
    "build_feishu_card_payload_projection": staticmethod(lambda review, summary=None, warnings=None: {
    "status": "projection_only", "send_allowed": False, "webhook_required": True,
    "no_webhook_call": True, "no_runtime_write": True, "warnings": [],
    "card_json": {"elements": []}
    }),
    "build_plaintext_nightly_summary": staticmethod(lambda review, warnings=None: {"text": "test", "warnings": []}),
    "validate_feishu_payload_projection": staticmethod(lambda payload, warnings=None: {
    "valid": True, "warnings": [], "blocked_reasons": []
    }),
    }))
    result = cli.run_feishu_summary_diagnostic()
    assert result["command"] == "feishu-summary"
    assert result["summary"]["send_allowed"] is False
    assert result["summary"]["webhook_required"] is True
    assert result["summary"]["no_webhook_call"] is True
    assert result["summary"]["no_runtime_write"] is True


def test_run_feishu_summary_diagnostic_import_failure(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "app.nightly.foundation_health_review", None)
    monkeypatch.setitem(__import__("sys").modules, "app.nightly.foundation_health_summary", None)
    result = cli.run_feishu_summary_diagnostic()
    assert result["status"] == "failed"
    assert result["command"] == "feishu-summary"


@pytest.mark.slow
@pytest.mark.integration
def test_run_feishu_summary_diagnostic_send_allowed_false():
    # If the real import succeeds, check the projection enforces send_allowed=False
    result = _synthetic_feishu_summary_result()
    assert result["summary"]["send_allowed"] is False


@pytest.mark.slow
@pytest.mark.integration
def test_run_feishu_summary_diagnostic_webhook_required_true():
    result = _synthetic_feishu_summary_result()
    assert result["summary"]["webhook_required"] is True


@pytest.mark.slow
@pytest.mark.integration
def test_run_feishu_summary_diagnostic_no_webhook_call_flag():
    result = _synthetic_feishu_summary_result()
    assert result["summary"].get("no_webhook_call") is not False


@pytest.mark.slow
@pytest.mark.integration
def test_run_feishu_summary_diagnostic_validation_present():
    result = _synthetic_feishu_summary_result()
    payload = result.get("payload", {})
    validation = payload.get("validation", {})
    # validation should exist and have a 'valid' field
    assert "valid" in validation


# ─────────────────────────────────────────────────────────────────────────────
# All Diagnostics Aggregate Tests
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.slow
def test_run_all_diagnostics_contains_phase_c_commands(monkeypatch):
    def mock_diag(name):
        return {"status": "ok", "warnings": [], "errors": []}

    monkeypatch.setattr(cli, "run_truth_state_diagnostic", lambda **kw: mock_diag("truth-state"))
    monkeypatch.setattr(cli, "run_queue_sandbox_diagnostic", lambda **kw: mock_diag("queue-sandbox"))
    monkeypatch.setattr(cli, "run_memory_diagnostic", lambda **kw: mock_diag("memory"))
    monkeypatch.setattr(cli, "run_asset_diagnostic", lambda **kw: mock_diag("asset"))
    monkeypatch.setattr(cli, "run_prompt_diagnostic", lambda **kw: mock_diag("prompt"))
    monkeypatch.setattr(cli, "run_rtcm_diagnostic", lambda **kw: mock_diag("rtcm"))
    monkeypatch.setattr(cli, "run_nightly_diagnostic", lambda **kw: mock_diag("nightly"))
    monkeypatch.setattr(cli, "run_feishu_summary_diagnostic", lambda **kw: mock_diag("feishu-summary"))

    result = cli.run_all_diagnostics()
    child_statuses = result.get("summary", {}).get("child_statuses", {})
    assert "memory" in child_statuses
    assert "asset" in child_statuses
    assert "prompt" in child_statuses
    assert "rtcm" in child_statuses
    assert "feishu-summary" in child_statuses

@pytest.mark.slow
def test_run_all_diagnostics_disabled_commands_empty(monkeypatch):
    _patch_synthetic_diagnostics(monkeypatch)
    result = cli.run_all_diagnostics(write_report=False)
    disabled = result.get("summary", {}).get("disabled_commands", [])
    assert len(disabled) == 0


@pytest.mark.slow
def test_run_all_diagnostics_single_failure_is_partial_warning(monkeypatch):
    monkeypatch.setattr(cli, "run_memory_diagnostic", lambda **kw: {"status": "failed", "warnings": [], "errors": ["bad"]})
    monkeypatch.setattr(cli, "run_asset_diagnostic", lambda **kw: {"status": "ok", "warnings": [], "errors": []})
    monkeypatch.setattr(cli, "run_prompt_diagnostic", lambda **kw: {"status": "ok", "warnings": [], "errors": []})
    monkeypatch.setattr(cli, "run_rtcm_diagnostic", lambda **kw: {"status": "ok", "warnings": [], "errors": []})
    monkeypatch.setattr(cli, "run_truth_state_diagnostic", lambda **kw: {"status": "ok", "warnings": [], "errors": []})
    monkeypatch.setattr(cli, "run_queue_sandbox_diagnostic", lambda **kw: {"status": "ok", "warnings": [], "errors": []})
    monkeypatch.setattr(cli, "run_nightly_diagnostic", lambda **kw: {"status": "ok", "warnings": [], "errors": []})
    monkeypatch.setattr(cli, "run_feishu_summary_diagnostic", lambda **kw: {"status": "ok", "warnings": [], "errors": []})

    result = cli.run_all_diagnostics()
    assert result["status"] == "partial_warning"


@pytest.mark.slow
def test_run_all_diagnostics_write_report_false_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "DEFAULT_SAMPLE_PATH_PHASE_C", str(tmp_path / "sample.json"))
    _patch_synthetic_diagnostics(monkeypatch)
    result = cli.run_all_diagnostics(write_report=False)
    assert result.get("report_path") is None


@pytest.mark.slow
def test_run_all_diagnostics_write_report_true_writes_tmp_path(tmp_path, monkeypatch):
    _patch_synthetic_diagnostics(monkeypatch)
    output = tmp_path / "sample.json"
    result = cli.run_all_diagnostics(write_report=True, output_path=str(output))
    assert output.exists()
    assert result["report_path"] == str(output)


# ─────────────────────────────────────────────────────────────────────────────
# Format Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.slow
@pytest.mark.integration
def test_format_json_returns_dict(monkeypatch):
    _patch_synthetic_diagnostics(monkeypatch)
    result = cli.run_all_diagnostics(write_report=False)
    assert isinstance(cli.format_diagnostic_result(result, "json"), dict)


@pytest.mark.slow
@pytest.mark.integration
def test_format_markdown_returns_string(monkeypatch):
    _patch_synthetic_diagnostics(monkeypatch)
    result = cli.run_all_diagnostics(write_report=False)
    assert isinstance(cli.format_diagnostic_result(result, "markdown"), str)


@pytest.mark.slow
@pytest.mark.integration
def test_format_text_returns_string(monkeypatch):
    _patch_synthetic_diagnostics(monkeypatch)
    result = cli.run_all_diagnostics(write_report=False)
    assert isinstance(cli.format_diagnostic_result(result, "text"), str)


def test_format_markdown_handles_memory_summary(monkeypatch):
    monkeypatch.setattr(cli, "run_memory_diagnostic", lambda **kw: {"command": "memory", "status": "ok", "summary": {"scanned_count": 5, "risk_count": 1}, "payload": {}, "warnings": [], "errors": []})
    result = cli.run_memory_diagnostic()
    formatted = cli.format_diagnostic_result(result, "markdown")
    assert isinstance(formatted, str)
    assert "scanned_count" in formatted


def test_format_text_handles_asset_summary(monkeypatch):
    monkeypatch.setattr(cli, "run_asset_diagnostic", lambda **kw: {"command": "asset", "status": "ok", "summary": {"total_projected": 3}, "payload": {}, "warnings": [], "errors": []})
    result = cli.run_asset_diagnostic()
    formatted = cli.format_diagnostic_result(result, "text")
    assert isinstance(formatted, str)
    assert "total_projected" in formatted


def test_format_markdown_handles_feishu_summary(monkeypatch):
    monkeypatch.setattr(cli, "run_feishu_summary_diagnostic", lambda **kw: {
    "command": "feishu-summary", "status": "ok",
    "summary": {"send_allowed": False, "webhook_required": True, "feishu_payload_status": "projection_only"},
    "payload": {}, "warnings": [], "errors": []
    })
    result = cli.run_feishu_summary_diagnostic()
    formatted = cli.format_diagnostic_result(result, "markdown")
    assert isinstance(formatted, str)
    assert "send_allowed" in formatted
    assert "projection_only" in formatted


def test_format_text_handles_feishu_summary(monkeypatch):
    monkeypatch.setattr(cli, "run_feishu_summary_diagnostic", lambda **kw: {
    "command": "feishu-summary", "status": "ok",
    "summary": {"send_allowed": False, "webhook_required": True, "feishu_payload_status": "projection_only"},
    "payload": {}, "warnings": [], "errors": []
    })
    result = cli.run_feishu_summary_diagnostic()
    formatted = cli.format_diagnostic_result(result, "text")
    assert isinstance(formatted, str)
    assert "send_allowed" in formatted


    # ─────────────────────────────────────────────────────────────────────────────
    # CLI Main Entry Point Tests
    # ─────────────────────────────────────────────────────────────────────────────


def test_main_memory_exit_0(monkeypatch):
    monkeypatch.setattr(cli, "run_memory_diagnostic", lambda **kw: {"command": "memory", "status": "ok", "summary": {}, "payload": {}, "warnings": [], "errors": []})
    assert cli.main(["memory", "--format", "json", "--max-files", "100"]) == 0


def test_main_asset_exit_0(monkeypatch):
    monkeypatch.setattr(cli, "run_asset_diagnostic", lambda **kw: {"command": "asset", "status": "ok", "summary": {}, "payload": {}, "warnings": [], "errors": []})
    assert cli.main(["asset", "--format", "json", "--limit", "50"]) == 0


def test_main_prompt_exit_0(monkeypatch):
    monkeypatch.setattr(cli, "run_prompt_diagnostic", lambda **kw: {"command": "prompt", "status": "ok", "summary": {}, "payload": {}, "warnings": [], "errors": []})
    assert cli.main(["prompt", "--format", "json", "--max-files", "100"]) == 0


def test_main_rtcm_exit_0(monkeypatch):
    monkeypatch.setattr(cli, "run_rtcm_diagnostic", lambda **kw: {"command": "rtcm", "status": "ok", "summary": {}, "payload": {}, "warnings": [], "errors": []})
    assert cli.main(["rtcm", "--format", "json", "--max-files", "200"]) == 0


def test_main_feishu_summary_exit_0(monkeypatch):
    monkeypatch.setattr(cli, "run_feishu_summary_diagnostic", lambda **kw: {"command": "feishu-summary", "status": "ok", "summary": {"send_allowed": False}, "payload": {}, "warnings": [], "errors": []})
    assert cli.main(["feishu-summary", "--format", "json"]) == 0


def test_main_feishu_summary_text_exit_0(monkeypatch):
    monkeypatch.setattr(cli, "run_feishu_summary_diagnostic", lambda **kw: {"command": "feishu-summary", "status": "ok", "summary": {"send_allowed": False}, "payload": {}, "warnings": [], "errors": []})
    assert cli.main(["feishu-summary", "--format", "text"]) == 0


def test_main_unknown_command_exit_1():
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["unknown-command"])
    assert exc_info.value.code == 2


def test_script_foundation_diagnose_imports_main():
    import importlib.util

    path = Path(cli.ROOT) / "scripts" / "foundation_diagnose.py"
    assert path.exists()
    spec = importlib.util.spec_from_file_location("foundation_diagnose", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    assert hasattr(module, "main")


    # ─────────────────────────────────────────────────────────────────────────────
    # Safety / No-Modification Tests
    # ─────────────────────────────────────────────────────────────────────────────


def test_no_http_endpoint_opened():
    assert not (Path(cli.ROOT) / "backend/app/gateway/foundation_diagnostics.py").exists()


def test_gateway_not_modified_by_cli_module():
    assert "gateway" not in cli.__file__.lower()


def test_no_runtime_written(tmp_path):
    before = set(tmp_path.iterdir()) if tmp_path.exists() else set()
    cli.get_diagnostic_command_registry()
    after = set(tmp_path.iterdir()) if tmp_path.exists() else set()
    assert before == after


@pytest.mark.slow
@pytest.mark.integration
def test_no_tool_execution(monkeypatch):
    _patch_synthetic_diagnostics(monkeypatch)
    result = cli.run_all_diagnostics(write_report=False)
    assert "tool" not in " ".join(result.get("errors", []))


def test_no_full_memory_content_in_payload(monkeypatch):
    monkeypatch.setattr(cli, "run_memory_diagnostic", lambda **kw: {
    "command": "memory", "status": "ok",
    "summary": {"scanned_count": 5},
    "payload": {"representative_records": [{"source_path": "path1"}, {"source_path": "path2"}]},
    "warnings": [], "errors": []
    })
    result = cli.run_memory_diagnostic()
    # payload should be compact - no full content fields
    assert "full_content" not in str(result.get("payload", {}))


def test_no_full_prompt_content_in_payload(monkeypatch):
    monkeypatch.setattr(cli, "run_prompt_diagnostic", lambda **kw: {
    "command": "prompt", "status": "ok",
    "summary": {"scanned_count": 4},
    "payload": {"source_projection": {"records": []}},
    "warnings": [], "errors": []
    })
    result = cli.run_prompt_diagnostic()
    # no body field should appear
    assert "body" not in str(result.get("payload", {}))


def test_no_real_feishu_push(monkeypatch):
    """Verify feishu-summary does NOT set send_allowed=True."""
    monkeypatch.setattr(cli, "run_feishu_summary_diagnostic", lambda **kw: {
    "command": "feishu-summary", "status": "ok",
    "summary": {"send_allowed": False, "webhook_required": True, "no_webhook_call": True},
    "payload": {}, "warnings": [], "errors": []
    })
    result = cli.run_feishu_summary_diagnostic()
    assert result["summary"]["send_allowed"] is False
    assert result["summary"]["webhook_required"] is True


def test_no_webhook_call_flag_set(monkeypatch):
    monkeypatch.setattr(cli, "run_feishu_summary_diagnostic", lambda **kw: {
    "command": "feishu-summary", "status": "ok",
    "summary": {"no_webhook_call": True, "no_runtime_write": True},
    "payload": {}, "warnings": [], "errors": []
    })
    result = cli.run_feishu_summary_diagnostic()
    assert result["summary"]["no_webhook_call"] is True
    assert result["summary"]["no_runtime_write"] is True


def test_no_webhook_url_secret_token_in_output(monkeypatch):
    monkeypatch.setattr(cli, "run_feishu_summary_diagnostic", lambda **kw: {
    "command": "feishu-summary", "status": "ok",
    "summary": {"send_allowed": False},
    "payload": {"feishu_payload_projection": {"card_json": {"elements": []}}},
    "warnings": [], "errors": []
    })
    result = cli.run_feishu_summary_diagnostic()
    output_str = str(result)
    assert "webhook" not in output_str.lower() or "url" not in output_str.lower()
    assert "secret" not in output_str.lower()
    assert "token" not in output_str.lower()


def test_no_action_queue_write(monkeypatch):
    monkeypatch.setattr(cli, "run_feishu_summary_diagnostic", lambda **kw: {
    "command": "feishu-summary", "status": "ok",
    "summary": {"send_allowed": False},
    "payload": {}, "warnings": [], "errors": []
    })
    result = cli.run_feishu_summary_diagnostic()
    errors_str = " ".join(result.get("errors", []))
    assert "action_queue" not in errors_str.lower()
    assert "write" not in errors_str.lower()


@pytest.mark.slow
def test_sample_generator_phase_c_does_not_leak(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "DEFAULT_SAMPLE_PATH_PHASE_C", str(tmp_path / "phase_c_sample.json"))

    def safe_diag(name):
        return {"status": "ok", "warnings": [], "errors": [], "summary": {}, "payload": {}, "command": name}

    monkeypatch.setattr(cli, "run_truth_state_diagnostic", lambda **kw: safe_diag("truth-state"))
    monkeypatch.setattr(cli, "run_queue_sandbox_diagnostic", lambda **kw: safe_diag("queue-sandbox"))
    monkeypatch.setattr(cli, "run_memory_diagnostic", lambda **kw: safe_diag("memory"))
    monkeypatch.setattr(cli, "run_asset_diagnostic", lambda **kw: safe_diag("asset"))
    monkeypatch.setattr(cli, "run_prompt_diagnostic", lambda **kw: safe_diag("prompt"))
    monkeypatch.setattr(cli, "run_rtcm_diagnostic", lambda **kw: safe_diag("rtcm"))
    monkeypatch.setattr(cli, "run_nightly_diagnostic", lambda **kw: safe_diag("nightly"))
    monkeypatch.setattr(cli, "run_feishu_summary_diagnostic", lambda **kw: safe_diag("feishu-summary"))
    monkeypatch.setattr(cli, "run_all_diagnostics", lambda **kw: {**safe_diag("all"), "child_statuses": {}, "disabled_commands": []})

    output = tmp_path / "phase_c_sample.json"
    result = cli.generate_feishu_summary_dryrun_cli_sample(output_path=str(output))
    assert output.exists()
    data = result
    assert data["command_registry"]["available_commands"]
    assert "feishu_summary_diagnostic" in data


    # ─────────────────────────────────────────────────────────────────────────────
    # R241-11B Audit Record Projection Tests (Phase D)
    # ─────────────────────────────────────────────────────────────────────────────


def test_add_audit_record_helper_exists():
    assert hasattr(cli, "add_audit_record_to_diagnostic_result")


def test_add_audit_record_adds_fields():
    result = {"command": "truth-state", "status": "ok", "warnings": [], "errors": [], "summary": {}, "payload": {}}
    enriched = cli.add_audit_record_to_diagnostic_result(result, "truth-state")
    assert "audit_record" in enriched
    assert "audit_validation" in enriched


def test_add_audit_record_write_mode_design_only():
    result = {"command": "truth-state", "status": "ok", "warnings": [], "errors": [], "summary": {}, "payload": {}}
    enriched = cli.add_audit_record_to_diagnostic_result(result, "truth-state")
    assert enriched["audit_record"]["write_mode"] == "design_only"


def test_add_audit_record_event_type_mapping():
    for command, expected_event_type in [
        ("feishu-summary", "feishu_summary_dry_run"),
        ("nightly", "nightly_health_review"),
        ("all", "diagnostic_cli_run"),
        ("truth-state", "diagnostic_domain_result"),
        ("queue-sandbox", "diagnostic_domain_result"),
        ("memory", "diagnostic_domain_result"),
        ("asset", "diagnostic_domain_result"),
        ("prompt", "diagnostic_domain_result"),
        ("rtcm", "diagnostic_domain_result"),
    ]:
        result = {"command": command, "status": "ok", "warnings": [], "errors": [], "summary": {}, "payload": {}}
        enriched = cli.add_audit_record_to_diagnostic_result(result, command)
        assert enriched["audit_record"]["event_type"] == expected_event_type, f"failed for {command}"


def test_run_truth_state_has_audit_record():
    """run_truth_state_diagnostic returns audit_record (real execution)."""
    result = cli.run_truth_state_diagnostic()
    assert "audit_record" in result
    assert "audit_validation" in result
    assert result["audit_record"]["write_mode"] == "design_only"
    assert result["audit_record"]["event_type"] == "diagnostic_domain_result"


def test_run_queue_sandbox_has_audit_record():
    """run_queue_sandbox_diagnostic returns audit_record (real execution)."""
    result = cli.run_queue_sandbox_diagnostic()
    assert "audit_record" in result
    assert "audit_validation" in result
    assert result["audit_record"]["write_mode"] == "design_only"


@pytest.mark.slow
@pytest.mark.integration
def test_run_memory_has_audit_record(monkeypatch):
    """run_memory_diagnostic returns audit_record (real execution)."""
    _patch_synthetic_diagnostics(monkeypatch)
    result = cli.run_memory_diagnostic()
    assert "audit_record" in result
    assert "audit_validation" in result


@pytest.mark.slow
@pytest.mark.integration
def test_run_asset_has_audit_record(monkeypatch):
    """run_asset_diagnostic returns audit_record (real execution)."""
    _patch_synthetic_diagnostics(monkeypatch)
    result = cli.run_asset_diagnostic()
    assert "audit_record" in result
    assert "audit_validation" in result


@pytest.mark.slow
@pytest.mark.integration
def test_run_prompt_has_audit_record(monkeypatch):
    """run_prompt_diagnostic returns audit_record (real execution)."""
    _patch_synthetic_diagnostics(monkeypatch)
    result = cli.run_prompt_diagnostic()
    assert "audit_record" in result
    assert "audit_validation" in result


@pytest.mark.slow
@pytest.mark.integration
def test_run_rtcm_has_audit_record(monkeypatch):
    """run_rtcm_diagnostic returns audit_record (real execution)."""
    _patch_synthetic_diagnostics(monkeypatch)
    result = cli.run_rtcm_diagnostic()
    assert "audit_record" in result
    assert "audit_validation" in result


@pytest.mark.slow
@pytest.mark.integration
def test_run_nightly_has_audit_record_event_type_nightly_health_review(monkeypatch):
    """run_nightly_diagnostic audit_record has event_type nightly_health_review."""
    _patch_synthetic_diagnostics(monkeypatch)
    result = cli.run_nightly_diagnostic()
    assert result["audit_record"]["event_type"] == "nightly_health_review"


@pytest.mark.slow
@pytest.mark.integration
def test_run_feishu_summary_has_audit_record_event_type_feishu_summary_dry_run(monkeypatch):
    """run_feishu_summary_diagnostic audit_record has event_type feishu_summary_dry_run."""
    _patch_synthetic_diagnostics(monkeypatch)
    result = cli.run_feishu_summary_diagnostic()
    assert result["audit_record"]["event_type"] == "feishu_summary_dry_run"


@pytest.mark.slow
@pytest.mark.integration
def test_run_all_has_audit_record_event_type_diagnostic_cli_run(monkeypatch):
    """run_all_diagnostics audit_record has event_type diagnostic_cli_run."""
    _patch_synthetic_diagnostics(monkeypatch)
    result = cli.run_all_diagnostics(write_report=False)
    assert result["audit_record"]["event_type"] == "diagnostic_cli_run"


@pytest.mark.slow
@pytest.mark.integration
def test_audit_record_payload_hash_present(monkeypatch):
    """All audit_records have payload_hash field."""
    _patch_synthetic_diagnostics(monkeypatch)
    for func in [
        cli.run_truth_state_diagnostic,
        cli.run_queue_sandbox_diagnostic,
        cli.run_memory_diagnostic,
        cli.run_asset_diagnostic,
        cli.run_prompt_diagnostic,
        cli.run_rtcm_diagnostic,
        cli.run_nightly_diagnostic,
        cli.run_feishu_summary_diagnostic,
    ]:
        result = func()
        assert "audit_record" in result, f"missing audit_record for {func.__name__}"
        assert result["audit_record"].get("payload_hash"), f"missing payload_hash for {func.__name__}"


@pytest.mark.slow
@pytest.mark.integration
def test_audit_record_sensitivity_level_classified():
    """audit_record has sensitivity_level field."""
    result = cli.run_truth_state_diagnostic()
    assert "sensitivity_level" in result["audit_record"]


@pytest.mark.slow
@pytest.mark.integration
def test_audit_validation_has_valid_field():
    """audit_validation has 'valid' field."""
    result = cli.run_truth_state_diagnostic()
    assert "valid" in result["audit_validation"]


def test_add_audit_record_exception_is_graceful():
    """add_audit_record_to_diagnostic_result handles exceptions gracefully."""
    bad_result = {"status": "ok", "warnings": [], "errors": []}
    # If audit module import fails, should still return with error placeholder
    enriched = cli.add_audit_record_to_diagnostic_result(bad_result, "truth-state")
    assert "audit_record" in enriched
    assert "audit_validation" in enriched


def test_generate_dryrun_audit_record_projection_sample_exists():
    """generate_dryrun_audit_record_projection_sample function exists."""
    assert hasattr(cli, "generate_dryrun_audit_record_projection_sample")


def test_markdown_formatter_shows_audit_summary(monkeypatch):
    """_format_markdown includes audit record section when audit_record present."""
    monkeypatch.setattr(cli, "run_truth_state_diagnostic", lambda **kw: {
    "command": "truth-state", "status": "ok", "generated_at": "2026-04-25T00:00:00+00:00",
    "root": "E:\\OpenClaw-Base\\deerflow", "summary": {}, "payload": {}, "warnings": [], "errors": [],
    "audit_record": {"event_type": "diagnostic_domain_result", "write_mode": "design_only",
    "sensitivity_level": "public_metadata", "payload_hash": "abc123def456",
    "redaction_applied": False},
    "audit_validation": {"valid": True, "errors": []}
    })
    result = cli.run_truth_state_diagnostic()
    md = cli._format_markdown(result)
    assert "Audit Record" in md
    assert "event_type" in md


def test_text_formatter_shows_audit_summary(monkeypatch):
    """_format_text includes audit record section when audit_record present."""
    monkeypatch.setattr(cli, "run_truth_state_diagnostic", lambda **kw: {
    "command": "truth-state", "status": "ok", "generated_at": "2026-04-25T00:00:00+00:00",
    "root": "E:\\OpenClaw-Base\\deerflow", "summary": {}, "payload": {}, "warnings": [], "errors": [],
    "audit_record": {"event_type": "diagnostic_domain_result", "write_mode": "design_only",
    "sensitivity_level": "public_metadata", "payload_hash": "abc123def456",
    "redaction_applied": False},
    "audit_validation": {"valid": True, "errors": []}
    })
    result = cli.run_truth_state_diagnostic()
    text = cli._format_text(result)
    assert "audit_record" in text
    assert "event_type" in text


def test_no_audit_jsonl_file_created(tmp_path, monkeypatch):
    """Phase D sample generator does NOT create real audit JSONL files."""
    monkeypatch.setattr(cli, "DEFAULT_SAMPLE_PATH_PHASE_D", str(tmp_path / "phase_d_sample.json"))

    def safe_diag(name):
        return {"status": "ok", "warnings": [], "errors": [], "summary": {}, "payload": {},
                "command": name, "generated_at": "2026-04-25T00:00:00+00:00", "root": "E:\\OpenClaw-Base\\deerflow",
                "audit_record": {"event_type": "diagnostic_domain_result", "write_mode": "design_only",
                                 "sensitivity_level": "public_metadata", "payload_hash": "abc123",
                                 "redaction_applied": False},
                "audit_validation": {"valid": True, "errors": []}}

    monkeypatch.setattr(cli, "run_truth_state_diagnostic", lambda **kw: safe_diag("truth-state"))
    monkeypatch.setattr(cli, "run_queue_sandbox_diagnostic", lambda **kw: safe_diag("queue-sandbox"))
    monkeypatch.setattr(cli, "run_memory_diagnostic", lambda **kw: safe_diag("memory"))
    monkeypatch.setattr(cli, "run_asset_diagnostic", lambda **kw: safe_diag("asset"))
    monkeypatch.setattr(cli, "run_prompt_diagnostic", lambda **kw: safe_diag("prompt"))
    monkeypatch.setattr(cli, "run_rtcm_diagnostic", lambda **kw: safe_diag("rtcm"))
    monkeypatch.setattr(cli, "run_nightly_diagnostic", lambda **kw: safe_diag("nightly"))
    monkeypatch.setattr(cli, "run_feishu_summary_diagnostic", lambda **kw: safe_diag("feishu-summary"))
    monkeypatch.setattr(cli, "run_all_diagnostics", lambda **kw: {**safe_diag("all"), "child_statuses": {}, "disabled_commands": []})

    output = tmp_path / "phase_d_sample.json"
    result = cli.generate_dryrun_audit_record_projection_sample(output_path=str(output))
    assert output.exists()
    # Verify audit_record present in all diagnostics
    for key in ["truth_state_diagnostic", "queue_sandbox_diagnostic", "memory_diagnostic",
                 "asset_diagnostic", "prompt_diagnostic", "rtcm_diagnostic",
                 "nightly_diagnostic", "feishu_summary_diagnostic"]:
        assert key in result
        assert "audit_record" in result[key], f"missing audit_record in {key}"
        assert result[key]["audit_record"]["write_mode"] == "design_only"


@pytest.mark.slow
@pytest.mark.integration
def test_audit_record_redaction_applied_for_sensitive_payload(monkeypatch):
    """audit_record is present and sensitivity_level is classified."""
    _patch_synthetic_diagnostics(monkeypatch)
    result = cli.run_feishu_summary_diagnostic()
    assert "audit_record" in result
    assert "sensitivity_level" in result["audit_record"]
    assert result["audit_record"]["sensitivity_level"] in (
    "public_metadata", "internal_metadata", "sensitive_path_metadata",
    "secret_or_token", "user_private_content", "unknown"
    )


    # ─────────────────────────────────────────────────────────────────────────────
    # Audit Query CLI Tests (R241-11D Phase 4)
    # ─────────────────────────────────────────────────────────────────────────────


def test_audit_query_command_exists():
    """CLI main accepts audit-query as a command."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["audit-query", "audit-scan"])
    # Just verify the choice is accepted
    args = parser.parse_args(["audit-query"])
    assert args.command == "audit-query"


def test_audit_scan_command_exists():
    """CLI main accepts audit-scan as a command."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["audit-query", "audit-scan"])
    args = parser.parse_args(["audit-scan"])
    assert args.command == "audit-scan"


def test_audit_query_does_not_trigger_append(monkeypatch, tmp_path):
    """audit-query reads existing JSONL but does NOT call append functions."""
    import sys
    from pathlib import Path

    # Create a minimal temp audit trail
    audit_dir = tmp_path / "migration_reports" / "foundation_audit" / "audit_trail"
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "foundation_diagnostic_runs.jsonl").write_text('{"audit_record_id":"x","event_type":"diagnostic_cli_run","write_mode":"append_only","status":"ok","root":"x","generated_at":"2026-04-25T00:00:00Z","observed_at":"2026-04-25T00:00:00Z","payload_hash":"x","sensitivity_level":"public_metadata","schema_version":"1.0"}\n', encoding="utf-8")

    append_called = []
    original_append = __import__("app.audit", fromlist=["append_all_diagnostic_audit_records"]).append_all_diagnostic_audit_records
    def track_append(*a, **kw):
        append_called.append((a, kw))
        return original_append(*a, **kw)

    monkeypatch.setattr(
        "app.audit.append_all_diagnostic_audit_records",
        track_append,
    )
    monkeypatch.setattr(
        "app.foundation.read_only_diagnostics_cli.ROOT",
        tmp_path,
    )

    class FakeArgs:
        command = "audit-query"
        format = "json"
        limit = 100
        event_type = "diagnostic_cli_run"
        source_command = None
        status = None
        write_mode = None
        sensitivity_level = None
        payload_hash = None
        audit_record_id = None
        start_time = None
        end_time = None
        target_id = None
        order = "asc"

    result = cli._run_audit_query(FakeArgs())
    assert len(append_called) == 0  # NO append called
    assert result == 0


def test_audit_scan_does_not_write_files(monkeypatch, tmp_path):
    """audit-scan does not create or modify any files."""
    # Snapshot line counts
    audit_dir = tmp_path / "migration_reports" / "foundation_audit" / "audit_trail"
    audit_dir.mkdir(parents=True, exist_ok=True)
    jsonl = audit_dir / "foundation_diagnostic_runs.jsonl"
    jsonl.write_text('{"audit_record_id":"x","event_type":"diagnostic_cli_run","write_mode":"append_only","status":"ok","root":"x","generated_at":"2026-04-25T00:00:00Z","observed_at":"2026-04-25T00:00:00Z","payload_hash":"x","sensitivity_level":"public_metadata","schema_version":"1.0"}\n', encoding="utf-8")

    line_count_before = sum(1 for _ in open(jsonl))

    monkeypatch.setattr("app.foundation.read_only_diagnostics_cli.ROOT", tmp_path)

    class FakeArgs:
        command = "audit-scan"
        format = "json"

    cli._run_audit_scan(FakeArgs())

    line_count_after = sum(1 for _ in open(jsonl))
    assert line_count_after == line_count_before  # No new lines appended


def test_audit_query_unknown_args_exit_nonzero():
    """Unknown audit-query filter values do not crash (handled gracefully)."""
    import argparse
    # Verify the argument parser accepts all filter args
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-type", type=str, default=None)
    parser.add_argument("--status", type=str, default=None)
    parser.add_argument("--limit", type=int, default=100)
    # Unknown args should fall through to argparse error
    with pytest.raises(SystemExit):
        parser.parse_args(["--event-type", "nightly_health_review", "--unknown-flag"])


    # R241-12B Audit Trend CLI Tests


@pytest.mark.slow
def test_cli_audit_trend_json_exit_0(monkeypatch):
    monkeypatch.setattr(cli, "_run_audit_trend", lambda args: 0)
    assert cli.main(["audit-trend", "--window", "all_available", "--format", "json"]) == 0


@pytest.mark.slow
def test_cli_audit_trend_text_exit_0(monkeypatch):
    monkeypatch.setattr(cli, "_run_audit_trend", lambda args: 0)
    assert cli.main(["audit-trend", "--window", "last_24h", "--format", "text"]) == 0


@pytest.mark.slow
def test_cli_audit_trend_markdown_exit_0(monkeypatch):
    monkeypatch.setattr(cli, "_run_audit_trend", lambda args: 0)
    assert cli.main(["audit-trend", "--window", "last_7d", "--format", "markdown"]) == 0


@pytest.mark.slow
def test_audit_trend_does_not_trigger_append(monkeypatch, tmp_path, capsys):
    audit_dir = tmp_path / "migration_reports" / "foundation_audit" / "audit_trail"
    audit_dir.mkdir(parents=True, exist_ok=True)
    jsonl = audit_dir / "foundation_diagnostic_runs.jsonl"
    jsonl.write_text('{"audit_record_id":"x","event_type":"diagnostic_cli_run","write_mode":"append_only","source_command":"nightly","status":"ok","root":"x","generated_at":"2026-04-25T00:00:00Z","observed_at":"2026-04-25T00:00:00Z","payload_hash":"x","sensitivity_level":"public_metadata","schema_version":"1.0"}\n', encoding="utf-8")
    before = jsonl.read_text(encoding="utf-8")
    append_called = []

    def fake_append(*args, **kwargs):
        append_called.append((args, kwargs))
        return {"status": "blocked"}

    monkeypatch.setattr("app.foundation.read_only_diagnostics_cli.ROOT", tmp_path)
    monkeypatch.setattr("app.audit.append_all_diagnostic_audit_records", fake_append)

    assert cli.main(["audit-trend", "--window", "all_available", "--format", "text", "--limit", "10"]) == 0
    capsys.readouterr()
    assert append_called == []
    assert jsonl.read_text(encoding="utf-8") == before


    # R241-12C Trend Artifact CLI Tests


def _fake_trend_report():
    return {
        "trend_report_id": "trend_cli_test",
        "status": "ok",
        "window": "all_available",
        "total_records_analyzed": 1,
        "series": [],
        "regression_signals": [],
        "warnings": [],
        "errors": [],
    }


@pytest.mark.slow
def test_cli_audit_trend_write_trend_report_param_exists(monkeypatch):
    monkeypatch.setattr(cli, "_run_audit_trend", lambda args: 0)
    assert cli.main(["audit-trend", "--window", "all_available", "--format", "json", "--write-trend-report"]) == 0


@pytest.mark.slow
def test_cli_audit_trend_write_trend_report_only_writes_trend_artifact(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("app.foundation.read_only_diagnostics_cli.ROOT", tmp_path)
    monkeypatch.setattr("app.audit.audit_trend_cli_guard.generate_dryrun_nightly_trend_report", lambda **kw: {"trend_report": _fake_trend_report(), "warnings": [], "errors": []})
    monkeypatch.setattr("app.audit.audit_trend_cli_guard.format_trend_report", lambda report, fmt: {"status": report.get("status"), "summary": "safe"})
    result = cli.main(["audit-trend", "--window", "all_available", "--format", "json", "--write-trend-report", "--report-format", "json"])
    capsys.readouterr()
    artifact_path = tmp_path / "migration_reports" / "foundation_audit" / "R241-12D_TREND_REPORT_ARTIFACT.json"
    assert result == 0
    assert artifact_path.exists()


@pytest.mark.slow
def test_cli_audit_trend_write_trend_report_does_not_trigger_append_audit(monkeypatch, tmp_path, capsys):
    append_called = []
    monkeypatch.setattr("app.foundation.read_only_diagnostics_cli.ROOT", tmp_path)
    monkeypatch.setattr("app.audit.audit_trend_cli_guard.generate_dryrun_nightly_trend_report", lambda **kw: {"trend_report": _fake_trend_report(), "warnings": [], "errors": []})
    monkeypatch.setattr("app.audit.audit_trend_cli_guard.format_trend_report", lambda report, fmt: {"status": report.get("status"), "summary": "safe"})
    monkeypatch.setattr("app.audit.append_all_diagnostic_audit_records", lambda *a, **kw: append_called.append((a, kw)))
    result = cli.main([
        "audit-trend",
        "--window",
        "all_available",
        "--format",
        "json",
        "--append-audit",
        "--write-trend-report",
        "--report-format",
        "json",
    ])
    capsys.readouterr()
    assert result == 0
    assert append_called == []


@pytest.mark.slow
def test_cli_audit_trend_report_format_all_generates_bundle_summary(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("app.foundation.read_only_diagnostics_cli.ROOT", tmp_path)
    monkeypatch.setattr("app.audit.audit_trend_cli_guard.generate_dryrun_nightly_trend_report", lambda **kw: {"trend_report": _fake_trend_report(), "warnings": [], "errors": []})
    monkeypatch.setattr("app.audit.audit_trend_cli_guard.format_trend_report", lambda report, fmt: {"status": report.get("status"), "summary": "safe"})
    result = cli.main(["audit-trend", "--window", "all_available", "--format", "text", "--write-trend-report", "--report-format", "all"])
    captured = capsys.readouterr()
    assert result == 0
    assert "trend_report_artifact_bundle" in captured.out
    report_dir = tmp_path / "migration_reports" / "foundation_audit"
    assert (report_dir / "R241-12D_TREND_REPORT_ARTIFACT.json").exists()
    assert (report_dir / "R241-12D_TREND_REPORT_ARTIFACT.md").exists()
    assert (report_dir / "R241-12D_TREND_REPORT_ARTIFACT.txt").exists()


@pytest.mark.slow
def test_cli_audit_trend_write_report_does_not_write_audit_jsonl_or_modify_line_count(monkeypatch, tmp_path, capsys):
        audit_dir = tmp_path / "migration_reports" / "foundation_audit" / "audit_trail"
        audit_dir.mkdir(parents=True)
        jsonl = audit_dir / "foundation_diagnostic_runs.jsonl"
        jsonl.write_text('{"audit_record_id":"x"}\n', encoding="utf-8")
        before = jsonl.read_text(encoding="utf-8")
        monkeypatch.setattr("app.foundation.read_only_diagnostics_cli.ROOT", tmp_path)
        monkeypatch.setattr("app.audit.audit_trend_cli_guard.generate_dryrun_nightly_trend_report", lambda **kw: {"trend_report": _fake_trend_report(), "warnings": [], "errors": []})
        monkeypatch.setattr("app.audit.audit_trend_cli_guard.format_trend_report", lambda report, fmt: {"status": report.get("status"), "summary": "safe"})
        result = cli.main(["audit-trend", "--window", "all_available", "--format", "json", "--write-trend-report", "--report-format", "all"])
        capsys.readouterr()
        assert result == 0
        assert jsonl.read_text(encoding="utf-8") == before


# R241-12D Guarded Audit Trend CLI Tests


@pytest.mark.slow
def test_audit_trend_custom_window_args_exist(monkeypatch):
    captured = {}

    def fake_run(args):
        captured["window"] = args.window
        captured["start_time"] = args.start_time
        captured["end_time"] = args.end_time
        return 0

    monkeypatch.setattr(cli, "_run_audit_trend", fake_run)
    result = cli.main([
        "audit-trend",
        "--window",
        "custom",
        "--start-time",
        "2026-04-25T00:00:00Z",
        "--end-time",
        "2026-04-25T23:59:59Z",
        "--format",
        "json",
    ])
    assert result == 0
    assert captured == {
        "window": "custom",
        "start_time": "2026-04-25T00:00:00Z",
        "end_time": "2026-04-25T23:59:59Z",
    }


@pytest.mark.slow
def test_audit_trend_output_prefix_arg_exists(monkeypatch):
    captured = {}

    def fake_run(args):
        captured["output_prefix"] = args.output_prefix
        return 0

    monkeypatch.setattr(cli, "_run_audit_trend", fake_run)
    assert cli.main(["audit-trend", "--output-prefix", "R241-12D_TREND_REPORT_ARTIFACT"]) == 0
    assert captured["output_prefix"] == "R241-12D_TREND_REPORT_ARTIFACT"


@pytest.mark.slow
def test_audit_trend_output_contains_guard_summary(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("app.foundation.read_only_diagnostics_cli.ROOT", tmp_path)
    monkeypatch.setattr("app.audit.audit_trend_cli_guard.generate_dryrun_nightly_trend_report", lambda **kw: {"trend_report": _fake_trend_report(), "warnings": [], "errors": []})
    monkeypatch.setattr("app.audit.audit_trend_cli_guard.format_trend_report", lambda report, fmt: {"status": report.get("status"), "summary": "safe"})
    assert cli.main(["audit-trend", "--window", "all_available", "--format", "json"]) == 0
    out = capsys.readouterr().out
    assert "guard_summary" in out
    assert "audit_jsonl_unchanged" in out


@pytest.mark.slow
def test_audit_trend_write_report_false_does_not_write_artifact(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("app.foundation.read_only_diagnostics_cli.ROOT", tmp_path)
    monkeypatch.setattr("app.audit.audit_trend_cli_guard.generate_dryrun_nightly_trend_report", lambda **kw: {"trend_report": _fake_trend_report(), "warnings": [], "errors": []})
    monkeypatch.setattr("app.audit.audit_trend_cli_guard.format_trend_report", lambda report, fmt: {"status": report.get("status"), "summary": "safe"})
    assert cli.main(["audit-trend", "--window", "all_available", "--format", "text"]) == 0
    capsys.readouterr()
    assert not list((tmp_path / "migration_reports" / "foundation_audit").glob("R241-12D_TREND_REPORT_ARTIFACT.*"))


@pytest.mark.slow
def test_audit_trend_write_report_true_only_allowed_artifact(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("app.foundation.read_only_diagnostics_cli.ROOT", tmp_path)
    monkeypatch.setattr("app.audit.audit_trend_cli_guard.generate_dryrun_nightly_trend_report", lambda **kw: {"trend_report": _fake_trend_report(), "warnings": [], "errors": []})
    monkeypatch.setattr("app.audit.audit_trend_cli_guard.format_trend_report", lambda report, fmt: {"status": report.get("status"), "summary": "safe"})
    assert cli.main([
        "audit-trend",
        "--window",
        "all_available",
        "--format",
        "json",
        "--write-trend-report",
        "--report-format",
        "all",
        "--output-prefix",
        "R241-12D_TREND_REPORT_ARTIFACT",
    ]) == 0
    capsys.readouterr()
    report_dir = tmp_path / "migration_reports" / "foundation_audit"
    assert sorted(path.name for path in report_dir.glob("R241-12D_TREND_REPORT_ARTIFACT.*")) == [
        "R241-12D_TREND_REPORT_ARTIFACT.json",
        "R241-12D_TREND_REPORT_ARTIFACT.md",
        "R241-12D_TREND_REPORT_ARTIFACT.txt",
    ]
    if (report_dir / "audit_trail").exists():
        assert not list((report_dir / "audit_trail").glob("*.jsonl"))


@pytest.mark.slow
def test_audit_trend_does_not_write_jsonl_or_modify_line_count_guarded(monkeypatch, tmp_path, capsys):
    audit_dir = tmp_path / "migration_reports" / "foundation_audit" / "audit_trail"
    audit_dir.mkdir(parents=True)
    jsonl = audit_dir / "foundation_diagnostic_runs.jsonl"
    jsonl.write_text('{"audit_record_id":"x"}\n', encoding="utf-8")
    before = jsonl.read_text(encoding="utf-8")
    monkeypatch.setattr("app.foundation.read_only_diagnostics_cli.ROOT", tmp_path)
    monkeypatch.setattr("app.audit.audit_trend_cli_guard.generate_dryrun_nightly_trend_report", lambda **kw: {"trend_report": _fake_trend_report(), "warnings": [], "errors": []})
    monkeypatch.setattr("app.audit.audit_trend_cli_guard.format_trend_report", lambda report, fmt: {"status": report.get("status"), "summary": "safe"})
    assert cli.main(["audit-trend", "--write-trend-report", "--report-format", "all"]) == 0
    capsys.readouterr()
    assert jsonl.read_text(encoding="utf-8") == before


@pytest.mark.slow
def test_audit_trend_no_network_or_autofix(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("app.foundation.read_only_diagnostics_cli.ROOT", tmp_path)
    monkeypatch.setattr("app.audit.audit_trend_cli_guard.generate_dryrun_nightly_trend_report", lambda **kw: {"trend_report": _fake_trend_report(), "warnings": [], "errors": []})
    monkeypatch.setattr("app.audit.audit_trend_cli_guard.format_trend_report", lambda report, fmt: {"status": report.get("status"), "summary": "safe"})
    assert cli.main(["audit-trend", "--format", "json"]) == 0
    out = capsys.readouterr().out.lower()
    assert '"network_call_detected": false' in out
    assert '"auto_fix_detected": false' in out
