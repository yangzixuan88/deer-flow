"""Unified OpenClaw operator CLI — dry-run console.

Provides a single entry point for all tracked dry-run runtimes:
- Nightly Review
- Asset Runtime
- RTCM Roundtable

Safety guarantees:
- dry-run only — never sends real messages
- no token access — never reads token_cache.json
- no .deerflow/rtcm access — never reads operational data
- no Agent-S invocation
- no external network calls
- no daemon / background worker auto-start

Usage:
    python -m app.openclaw_cli.console list
    python -m app.openclaw_cli.console capability-summary
    python -m app.openclaw_cli.console nightly-dry-run
    python -m app.openclaw_cli.console asset-dry-run
    python -m app.openclaw_cli.console rtcm-dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .commands import (
    OperatorCommandResult,
    command_to_dict,
    list_commands,
)
from .runtimes import (
    preview_nightly_schedule,
    run_asset_dry_run,
    run_nightly_dry_run,
    run_nightly_export,
    run_nightly_run_once_preview,
    run_rtcm_dry_run,
    run_rtcm_dry_run_export,
    run_rtcm_report_index,
)


def capability_summary() -> OperatorCommandResult:
    """Build a capability summary for all tracked runtimes.

    Returns a summary of all available dry-run capabilities.
    """
    commands = list_commands()

    nightly_cmds = [c for c in commands if c.category == "nightly"]
    asset_cmds = [c for c in commands if c.category == "asset"]
    rtcm_cmds = [c for c in commands if c.category == "rtcm"]

    return OperatorCommandResult(
        command="capability-summary",
        status="success",
        dry_run=True,
        payload={
            "openclaw_version": "vNext",
            "cli_type": "operator_dry_run_console",
            "runtimes": {
                "nightly_review": {
                    "status": "AVAILABLE_WITH_LIMITS",
                    "commands": [c.name for c in nightly_cmds],
                    "dry_run": True,
                    "real_send": False,
                    "daemon": False,
                },
                "asset_runtime": {
                    "status": "AVAILABLE_WITH_LIMITS",
                    "commands": [c.name for c in asset_cmds],
                    "dry_run": True,
                    "agent_s": False,
                },
                "rtcm_roundtable": {
                    "status": "AVAILABLE_WITH_LIMITS",
                    "commands": [c.name for c in rtcm_cmds],
                    "dry_run": True,
                    "real_agents": False,
                },
            },
            "all_commands": [command_to_dict(c) for c in commands],
        },
        warnings=[],
    )


def run_command(name: str, **kwargs: object) -> OperatorCommandResult:
    """Dispatch a named command with optional keyword arguments.

    Args:
        name: Command name (e.g. "nightly-dry-run", "asset-dry-run")
        **kwargs: Additional arguments passed to the runtime wrapper.

    Returns:
        OperatorCommandResult from the executed command.

    Raises:
        ValueError: If the command name is unknown.
    """
    if name == "capability-summary":
        return capability_summary()
    elif name == "nightly-dry-run":
        store_path = kwargs.get("store_path")
        limit = kwargs.get("limit")
        return run_nightly_dry_run(store_path=store_path, limit=limit)
    elif name == "nightly-schedule-preview":
        return preview_nightly_schedule()
    elif name == "nightly-export":
        store = kwargs.get("store_path")
        output = kwargs.get("output")
        if not output:
            raise ValueError("--output is required for nightly-export")
        return run_nightly_export(store=store, output=output, limit=kwargs.get("limit"))
    elif name == "nightly-run-once-preview":
        store = kwargs.get("store_path")
        return run_nightly_run_once_preview(store=store, limit=kwargs.get("limit"))
    elif name == "asset-dry-run":
        return run_asset_dry_run(
            capability=kwargs.get("capability"),
            payload_summary=str(kwargs.get("payload_summary", "OpenClaw operator dry-run")),
        )
    elif name == "rtcm-dry-run":
        return run_rtcm_dry_run(topic=str(kwargs.get("topic", "OpenClaw operator dry-run roundtable")))
    elif name == "rtcm-dry-run-export":
        output = kwargs.get("output")
        if not output:
            raise ValueError("--output is required for rtcm-dry-run-export")
        return run_rtcm_dry_run_export(output=output)
    elif name == "rtcm-report-index":
        store = kwargs.get("store")
        if not store:
            raise ValueError("--store is required for rtcm-report-index")
        return run_rtcm_report_index(store=store, limit=kwargs.get("limit"))
    else:
        raise ValueError(f"Unknown command: {name}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deerflow openclaw",
        description="OpenClaw operator dry-run console — Nightly / Asset / RTCM",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # list
    subparsers.add_parser("list", help="List all available commands")

    # capability-summary
    cap_parser = subparsers.add_parser("capability-summary", help="Show capability summary")
    cap_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    # nightly-dry-run
    nightly_parser = subparsers.add_parser("nightly-dry-run", help="Run Nightly Review dry-run")
    nightly_parser.add_argument("--store-path", default=None, help="Path to NightlyReviewStore JSONL")
    nightly_parser.add_argument("--limit", type=int, default=None, help="Limit number of items")

    # nightly-schedule-preview
    subparsers.add_parser("nightly-schedule-preview", help="Preview Nightly schedule capability")

    # nightly-export
    nightly_export_parser = subparsers.add_parser("nightly-export", help="Export Nightly Review as markdown report")
    nightly_export_parser.add_argument(
        "--store-path",
        type=Path,
        default=None,
        help="Path to NightlyReviewStore JSONL (optional; uses in-memory if not set)",
    )
    nightly_export_parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output path for the markdown report",
    )
    nightly_export_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of items to include",
    )

    # nightly-run-once-preview
    nightly_runonce_parser = subparsers.add_parser(
        "nightly-run-once-preview",
        help="Build Nightly Review payload without sending (dry-run preview)",
    )
    nightly_runonce_parser.add_argument(
        "--store-path",
        type=Path,
        default=None,
        help="Path to NightlyReviewStore JSONL (optional; uses in-memory if not set)",
    )
    nightly_runonce_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of items to include",
    )

    # asset-dry-run
    asset_parser = subparsers.add_parser("asset-dry-run", help="Run Asset dry-run")
    asset_parser.add_argument("--capability", default=None, help="Override capability name")
    asset_parser.add_argument(
        "--payload-summary",
        default="OpenClaw operator dry-run",
        help="Human-readable summary for the dry-run",
    )

    # rtcm-dry-run
    rtcm_parser = subparsers.add_parser("rtcm-dry-run", help="Run RTCM roundtable dry-run")
    rtcm_parser.add_argument(
        "--topic",
        default="OpenClaw operator dry-run roundtable",
        help="Topic for the roundtable",
    )

    # rtcm-dry-run-export
    rtcm_export_parser = subparsers.add_parser("rtcm-dry-run-export", help="Run RTCM dry-run and export markdown report")
    rtcm_export_parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output path for the markdown report",
    )

    # rtcm-report-index
    rtcm_index_parser = subparsers.add_parser("rtcm-report-index", help="Build JSON index from RTCM store")
    rtcm_index_parser.add_argument(
        "--store",
        type=Path,
        required=True,
        help="Path to the RTCMDecisionStore JSONL file",
    )
    rtcm_index_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of records to include (most recent first)",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the OpenClaw operator CLI.

    Args:
        argv: Optional argument list. If None, uses sys.argv.

    Returns:
        Exit code: 0 for success, 1 for error, 2 for --real rejection.
    """
    parser = _build_parser()

    # Parse with allow_abbrev=False to prevent argparse from consuming --real
    # as a prefix of something else; handle --real manually.
    args, unknowns = parser.parse_known_args(argv)

    # Reject --real if it appears anywhere in argv
    if "--real" in (argv or []):
        print(
            json.dumps(
                OperatorCommandResult(
                    command="",
                    status="error",
                    dry_run=True,
                    payload={},
                    warnings=["--real flag is not supported by OpenClaw operator CLI dry-run console"],
                ).to_dict(),
                indent=2,
            ),
            file=sys.stdout,
        )
        return 2

    # Default: show help
    if args.command is None:
        parser.print_help()
        return 0

    # Dispatch commands
    try:
        if args.command == "list":
            commands = list_commands()
            output = {
                "commands": [command_to_dict(c) for c in commands],
                "total": len(commands),
            }
            print(json.dumps(output, indent=2))
            return 0

        elif args.command == "capability-summary":
            result = capability_summary()
            print(json.dumps(result.to_dict(), indent=2))
            return 0

        elif args.command == "nightly-dry-run":
            result = run_nightly_dry_run(
                store_path=args.store_path,
                limit=args.limit,
            )
            print(json.dumps(result.to_dict(), indent=2))
            return 0

        elif args.command == "nightly-schedule-preview":
            result = preview_nightly_schedule()
            print(json.dumps(result.to_dict(), indent=2))
            return 0

        elif args.command == "nightly-export":
            result = run_nightly_export(
                store=args.store_path,
                output=args.output,
                limit=args.limit,
            )
            print(json.dumps(result.to_dict(), indent=2))
            return 0

        elif args.command == "nightly-run-once-preview":
            result = run_nightly_run_once_preview(
                store=args.store_path,
                limit=args.limit,
            )
            print(json.dumps(result.to_dict(), indent=2))
            return 0

        elif args.command == "asset-dry-run":
            result = run_asset_dry_run(
                capability=args.capability,
                payload_summary=args.payload_summary,
            )
            print(json.dumps(result.to_dict(), indent=2))
            return 0

        elif args.command == "rtcm-dry-run":
            result = run_rtcm_dry_run(topic=args.topic)
            print(json.dumps(result.to_dict(), indent=2))
            return 0

        elif args.command == "rtcm-dry-run-export":
            result = run_rtcm_dry_run_export(output=args.output)
            print(json.dumps(result.to_dict(), indent=2))
            return 0

        elif args.command == "rtcm-report-index":
            result = run_rtcm_report_index(store=args.store, limit=args.limit)
            print(json.dumps(result.to_dict(), indent=2))
            return 0

        else:
            print(json.dumps({"error": f"Unknown command: {args.command}"}), file=sys.stderr)
            return 1

    except Exception as e:
        print(json.dumps({"error": str(e), "command": args.command}, indent=2), file=sys.stderr)
        return 1


__all__ = [
    "capability_summary",
    "main",
    "run_command",
    "OperatorCommandResult",
]
