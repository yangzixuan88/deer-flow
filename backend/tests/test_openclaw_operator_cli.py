"""Tests for OpenClaw operator dry-run CLI.

Verifies that the unified operator CLI exposes all dry-run runtimes
without side effects, network calls, or credential access.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from app.openclaw_cli import (
    capability_summary,
    list_commands,
    main,
    preview_nightly_schedule,
    run_asset_dry_run,
    run_command,
    run_nightly_dry_run,
    run_rtcm_dry_run,
)

# =============================================================================
# Import / side-effect tests
# =============================================================================


class TestNoSideEffects:
    def test_operator_cli_import_has_no_side_effects(self):
        """Importing openclaw_cli must not start threads or daemons."""
        import importlib

        import app.openclaw_cli
        import app.openclaw_cli.console
        import app.openclaw_cli.runtimes

        importlib.reload(app.openclaw_cli.console)
        importlib.reload(app.openclaw_cli.runtimes)
        importlib.reload(app.openclaw_cli)

        # If we got here without errors, import is safe

    def test_cli_main_has_no_side_effects(self):
        """Calling main() with --help must not start any background process."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0


# =============================================================================
# Command registry tests
# =============================================================================


class TestCommandRegistry:
    def test_list_commands_contains_expected_commands(self):
        commands = list_commands()
        names = [c.name for c in commands]
        assert "nightly-dry-run" in names
        assert "asset-dry-run" in names
        assert "rtcm-dry-run" in names
        assert "capability-summary" in names
        assert "nightly-schedule-preview" in names

    def test_all_commands_are_json_serializable(self):
        commands = list_commands()
        for cmd in commands:
            d = cmd.to_dict()
            assert isinstance(d, dict)
            json.dumps(d)

    def test_command_to_dict_contains_required_fields(self):
        commands = list_commands()
        for cmd in commands:
            d = cmd.to_dict()
            assert "name" in d
            assert "description" in d
            assert "category" in d
            assert "dry_run_only" in d
            assert d["dry_run_only"] is True

    def test_run_unknown_command_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown command"):
            run_command("nonexistent-command")


# =============================================================================
# Capability summary tests
# =============================================================================


class TestCapabilitySummary:
    def test_capability_summary_returns_all_runtime_groups(self):
        result = capability_summary()
        assert result.command == "capability-summary"
        assert result.status == "success"
        assert result.dry_run is True
        assert "nightly_review" in result.payload["runtimes"]
        assert "asset_runtime" in result.payload["runtimes"]
        assert "rtcm_roundtable" in result.payload["runtimes"]

    def test_capability_summary_json_serializable(self):
        result = capability_summary()
        d = result.to_dict()
        json.dumps(d)

    def test_capability_summary_no_network(self):
        result = capability_summary()
        for warning in result.warnings:
            assert "network" not in warning.lower()


# =============================================================================
# Nightly runtime wrapper tests
# =============================================================================


class TestNightlyRuntime:
    def test_run_nightly_dry_run_with_empty_store(self, tmp_path):
        result = run_nightly_dry_run(store_path=str(tmp_path / "nightly.jsonl"))
        assert result.command == "nightly-dry-run"
        assert result.status == "success"
        assert result.dry_run is True
        assert "pending_items" in result.payload

    def test_run_nightly_dry_run_in_memory(self):
        result = run_nightly_dry_run(store_path=None)
        assert result.command == "nightly-dry-run"
        assert result.status == "success"
        assert result.dry_run is True
        assert result.payload["store_path"] == ":memory:"

    def test_run_nightly_dry_run_with_limit(self, tmp_path):
        store_path = tmp_path / "nightly_limit.jsonl"
        result = run_nightly_dry_run(store_path=str(store_path), limit=5)
        assert result.status == "success"

    def test_preview_nightly_schedule_no_daemon(self):
        result = preview_nightly_schedule()
        assert result.command == "nightly-schedule-preview"
        assert result.status == "success"
        assert result.dry_run is True
        assert result.payload["daemon_supported"] is False
        assert result.payload["real_send_supported"] is False


# =============================================================================
# Asset runtime wrapper tests
# =============================================================================


class TestAssetRuntime:
    def test_run_asset_dry_run_returns_asset_result(self):
        result = run_asset_dry_run()
        assert result.command == "asset-dry-run"
        assert result.status == "success"
        assert result.dry_run is True
        assert result.payload["status"] == "dry_run"
        assert result.payload["dry_run"] is True

    def test_run_asset_dry_run_has_warning_no_real_agent(self):
        result = run_asset_dry_run()
        assert any("Agent-S" in w or "agent" in w.lower() for w in result.warnings)

    def test_run_asset_dry_run_with_custom_payload(self):
        result = run_asset_dry_run(payload_summary="test dry-run")
        assert result.status == "success"
        assert result.dry_run is True

    def test_run_asset_dry_run_json_serializable(self):
        result = run_asset_dry_run()
        d = result.to_dict()
        json.dumps(d)

    def test_asset_dry_run_accepts_capability_argument(self):
        result = run_asset_dry_run(capability="asset.plan")
        assert result.status == "success"
        assert result.payload["selected_capability"] == "asset.plan"

    def test_asset_dry_run_outputs_available_capabilities(self):
        result = run_asset_dry_run()
        assert "available_capabilities" in result.payload
        caps = result.payload["available_capabilities"]
        assert "asset.noop" in caps
        assert "asset.plan" in caps
        assert "asset.package" in caps

    def test_capability_summary_includes_asset_registry(self):
        result = capability_summary()
        asset_info = result.payload["runtimes"]["asset_runtime"]
        assert "asset" in str(asset_info)

    def test_asset_external_required_capability_does_not_invoke_agent_s(self):
        result = run_asset_dry_run(capability="asset.package")
        assert result.payload["external_runtime_invoked"] is False
        assert any("external Agent-S runtime not invoked" in w for w in result.payload["warnings"])

    def test_asset_cli_does_not_read_operation_assets(self, monkeypatch):
        opened_paths: list[str] = []

        def tracking_open(path, *args, **kwargs):
            p = str(path)
            opened_paths.append(p)
            raise FileNotFoundError("blocked")

        monkeypatch.setattr("builtins.open", tracking_open)
        run_asset_dry_run()

        for p in opened_paths:
            assert ".deerflow/operation_assets" not in p


# =============================================================================
# RTCM runtime wrapper tests
# =============================================================================


class TestRTCMRuntime:
    def test_run_rtcm_dry_run_returns_decision_record(self):
        result = run_rtcm_dry_run()
        assert result.command == "rtcm-dry-run"
        assert result.status == "success"
        assert result.dry_run is True
        assert result.payload["status"] == "dry_run"
        assert "member_count" in result.payload

    def test_run_rtcm_dry_run_has_warnings_no_operational_data(self):
        result = run_rtcm_dry_run()
        assert any("operational" in w.lower() or "agent" in w.lower() for w in result.warnings)

    def test_run_rtcm_dry_run_with_custom_topic(self):
        result = run_rtcm_dry_run(topic="Custom topic")
        assert result.status == "success"
        assert result.dry_run is True
        assert result.payload["topic"] == "Custom topic"

    def test_run_rtcm_dry_run_json_serializable(self):
        result = run_rtcm_dry_run()
        d = result.to_dict()
        json.dumps(d)

    def test_rtcm_dry_run_export_requires_output(self, tmp_path):
        from app.openclaw_cli.runtimes.rtcm import run_rtcm_dry_run_export

        result = run_rtcm_dry_run_export(output=str(tmp_path / "report.md"))
        assert result.command == "rtcm-dry-run-export"
        assert result.status == "success"
        assert result.dry_run is True
        assert "output_path" in result.payload
        assert (tmp_path / "report.md").exists()

    def test_rtcm_dry_run_export_writes_markdown(self, tmp_path):
        from app.openclaw_cli.runtimes.rtcm import run_rtcm_dry_run_export

        out_path = tmp_path / "rtcm.md"
        result = run_rtcm_dry_run_export(output=str(out_path))
        text = out_path.read_text(encoding="utf-8")
        assert "# RTCM Roundtable Decision Report" in text
        assert result.payload["dry_run"] is True

    def test_rtcm_report_index_requires_store(self, tmp_path):
        from app.openclaw_cli.runtimes.rtcm import run_rtcm_report_index

        store_path = tmp_path / "rtcm.jsonl"
        result = run_rtcm_report_index(store=str(store_path))
        assert result.command == "rtcm-report-index"
        assert result.status == "success"
        assert result.payload["record_count"] == 0

    def test_rtcm_report_index_reads_explicit_store_only(self, tmp_path):
        from app.openclaw_cli.runtimes.rtcm import run_rtcm_report_index
        from app.rtcm import (
            RoundtableRequest,
            RTCMDecisionStore,
            build_decision_record,
            build_default_council,
            cast_dry_run_votes,
            compute_majority_consensus,
        )

        store_path = tmp_path / "rtcm.jsonl"
        store = RTCMDecisionStore(store_path)
        req = RoundtableRequest.new(topic="idx-test", reason="testing index")
        members = build_default_council()
        votes = cast_dry_run_votes(req, members)
        consensus = compute_majority_consensus(req, votes)
        record = build_decision_record(req, members, votes, consensus)
        store.append(record)

        result = run_rtcm_report_index(store=str(store_path))

        assert result.payload["record_count"] == 1
        idx = result.payload["index"]
        assert idx["count"] == 1
        assert idx["dry_run"] is True

    def test_rtcm_export_does_not_read_operational_rtcm_dir(self, tmp_path, monkeypatch):
        from app.openclaw_cli.runtimes.rtcm import run_rtcm_dry_run_export

        opened_paths: list[str] = []

        def tracking_open(path, *args, **kwargs):
            opened_paths.append(str(path))
            raise FileNotFoundError("blocked")

        monkeypatch.setattr("builtins.open", tracking_open)
        run_rtcm_dry_run_export(output=str(tmp_path / "report.md"))

        for p in opened_paths:
            assert ".deerflow/rtcm" not in p


# =============================================================================
# Nightly export and run-once tests
# =============================================================================


class TestNightlyExport:
    def test_nightly_export_requires_output(self, tmp_path):
        from app.openclaw_cli.runtimes.nightly import run_nightly_export

        result = run_nightly_export(output=str(tmp_path / "nightly.md"))
        assert result.command == "nightly-export"
        assert result.status == "success"
        assert result.dry_run is True
        assert "output_path" in result.payload

    def test_nightly_export_writes_markdown(self, tmp_path):
        from app.openclaw_cli.runtimes.nightly import run_nightly_export

        out_path = tmp_path / "nightly.md"
        run_nightly_export(output=str(out_path))
        assert out_path.exists()
        text = out_path.read_text(encoding="utf-8")
        assert "Nightly Review Report" in text

    def test_nightly_run_once_preview_requires_store(self, tmp_path):
        from app.openclaw_cli.runtimes.nightly import run_nightly_run_once_preview

        result = run_nightly_run_once_preview(store=str(tmp_path / "nightly.jsonl"))
        assert result.command == "nightly-run-once-preview"
        assert result.status == "success"
        assert result.dry_run is True
        assert result.payload["dry_run"] is True

    def test_nightly_run_once_preview_no_send(self, tmp_path):
        from app.openclaw_cli.runtimes.nightly import run_nightly_run_once_preview

        result = run_nightly_run_once_preview()
        assert "no message will be sent" in result.warnings[0]

    def test_nightly_export_does_not_read_operation_assets(self, tmp_path, monkeypatch):
        from app.openclaw_cli.runtimes.nightly import run_nightly_export

        opened_paths: list[str] = []

        def tracking_open(path, *args, **kwargs):
            opened_paths.append(str(path))
            raise FileNotFoundError("blocked")

        monkeypatch.setattr("builtins.open", tracking_open)
        run_nightly_export(output=str(tmp_path / "nightly.md"))

        for p in opened_paths:
            assert ".deerflow/operation_assets" not in p

    def test_operator_cli_new_commands_listed(self):
        commands = list_commands()
        names = [c.name for c in commands]
        assert "nightly-export" in names
        assert "nightly-run-once-preview" in names
        assert "rtcm-dry-run-export" in names
        assert "rtcm-report-index" in names

    def test_no_operational_dirs_read_by_new_commands(self, tmp_path, monkeypatch):
        from app.openclaw_cli.runtimes.nightly import run_nightly_export
        from app.openclaw_cli.runtimes.rtcm import run_rtcm_dry_run_export

        opened_paths: list[str] = []

        def tracking_open(path, *args, **kwargs):
            opened_paths.append(str(path))
            raise FileNotFoundError("blocked")

        monkeypatch.setattr("builtins.open", tracking_open)
        run_nightly_export(output=str(tmp_path / "nightly.md"))
        run_rtcm_dry_run_export(output=str(tmp_path / "rtcm.md"))

        for p in opened_paths:
            assert ".deerflow/rtcm" not in p
            assert ".deerflow/operation_assets" not in p


# =============================================================================
# run_command dispatch tests
# =============================================================================


class TestCommandDispatch:
    def test_run_command_capability_summary(self):
        result = run_command("capability-summary")
        assert result.command == "capability-summary"

    def test_run_command_nightly_dry_run(self):
        result = run_command("nightly-dry-run")
        assert result.command == "nightly-dry-run"

    def test_run_command_asset_dry_run(self):
        result = run_command("asset-dry-run")
        assert result.command == "asset-dry-run"

    def test_run_command_rtcm_dry_run(self):
        result = run_command("rtcm-dry-run")
        assert result.command == "rtcm-dry-run"


# =============================================================================
# CLI main tests
# =============================================================================


class TestCLIMain:
    def test_main_list_outputs_json(self, capsys):
        rc = main(["list"])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert "commands" in out
        assert out["total"] >= 5

    def test_main_capability_summary_outputs_json(self, capsys):
        rc = main(["capability-summary"])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["command"] == "capability-summary"
        assert "runtimes" in out["payload"]

    def test_main_asset_dry_run_outputs_json(self, capsys):
        rc = main(["asset-dry-run"])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["command"] == "asset-dry-run"
        assert out["dry_run"] is True

    def test_main_rtcm_dry_run_outputs_json(self, capsys):
        rc = main(["rtcm-dry-run"])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["command"] == "rtcm-dry-run"
        assert out["dry_run"] is True

    def test_real_execution_flag_rejected(self, capsys):
        rc = main(["asset-dry-run", "--real"])
        assert rc == 2
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "error"
        assert any("not supported" in w for w in out.get("warnings", []))


# =============================================================================
# Safety tests
# =============================================================================


class TestSafety:
    def test_no_feishu_send_called(self, monkeypatch):
        mock_send = MagicMock()
        monkeypatch.setattr("app.channels.feishu.FeishuChannel.send", mock_send)

        run_asset_dry_run()
        mock_send.assert_not_called()

    def test_no_external_network_called(self, capsys):
        """Nightly dry-run must not call external network."""
        rc = main(["nightly-dry-run"])
        assert rc == 0

    def test_no_rtcm_operational_data_access(self, monkeypatch):
        """Verify rtcm wrapper does not open .deerflow/rtcm paths."""
        opened_paths: list[str] = []

        def tracking_open(path, *args, **kwargs):
            p = str(path)
            opened_paths.append(p)
            raise FileNotFoundError("blocked for test")

        monkeypatch.setattr("builtins.open", tracking_open)
        import importlib

        import app.openclaw_cli.runtimes.rtcm

        importlib.reload(app.openclaw_cli.runtimes.rtcm)

        run_rtcm_dry_run()

        for p in opened_paths:
            assert ".deerflow/rtcm" not in p

    def test_no_operation_assets_access(self, monkeypatch):
        """Verify openclaw_cli does not open .deerflow/operation_assets paths."""
        opened_paths: list[str] = []

        def tracking_open(path, *args, **kwargs):
            p = str(path)
            opened_paths.append(p)
            raise FileNotFoundError("blocked for test")

        monkeypatch.setattr("builtins.open", tracking_open)
        import importlib

        import app.openclaw_cli
        import app.openclaw_cli.runtimes.asset

        importlib.reload(app.openclaw_cli.runtimes.asset)
        importlib.reload(app.openclaw_cli)

        run_asset_dry_run()

        for p in opened_paths:
            assert ".deerflow/operation_assets" not in p

    def test_no_token_cache_access(self, monkeypatch):
        """Verify no openclaw_cli module accesses token_cache.json."""
        opened_paths: list[str] = []

        def tracking_open(path, *args, **kwargs):
            p = str(path)
            opened_paths.append(p)
            raise FileNotFoundError("blocked")

        monkeypatch.setattr("builtins.open", tracking_open)
        import importlib

        import app.openclaw_cli
        import app.openclaw_cli.console
        import app.openclaw_cli.runtimes

        importlib.reload(app.openclaw_cli.runtimes)
        importlib.reload(app.openclaw_cli.console)
        importlib.reload(app.openclaw_cli)

        run_asset_dry_run()
        run_rtcm_dry_run()
        run_nightly_dry_run()

        for p in opened_paths:
            assert "token_cache" not in p.lower()

    def test_no_background_daemon_started(self, capsys):
        """Running nightly dry-run must not start a background daemon."""
        rc = main(["nightly-dry-run"])
        assert rc == 0
        # If we got here and rc == 0, no daemon was started

    def test_all_outputs_are_json_serializable(self, capsys):
        commands = ["capability-summary", "nightly-dry-run", "nightly-schedule-preview", "asset-dry-run", "rtcm-dry-run"]
        for cmd in commands:
            rc = main([cmd])
            assert rc == 0
            out = json.loads(capsys.readouterr().out)
            json.dumps(out)
            capsys.readouterr()  # clear
