"""Operator command registry for OpenClaw dry-run CLI.

Provides a typed command registry and result structures for the
unified operator CLI that exposes Nightly / Asset / RTCM dry-run capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OperatorCommand:
    """A registered operator CLI command."""

    name: str
    description: str
    category: str
    dry_run_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "dry_run_only": self.dry_run_only,
        }


@dataclass
class OperatorCommandResult:
    """Result of executing an operator command."""

    command: str
    status: str
    dry_run: bool
    payload: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "status": self.status,
            "dry_run": self.dry_run,
            "payload": self.payload,
            "warnings": self.warnings,
        }


# Registry of all available commands
_OPERATOR_COMMANDS: list[OperatorCommand] = [
    OperatorCommand(
        name="capability-summary",
        description="Show capability summary for all tracked runtimes",
        category="info",
        dry_run_only=True,
    ),
    OperatorCommand(
        name="nightly-dry-run",
        description="Run Nightly Review dry-run with optional store path",
        category="nightly",
        dry_run_only=True,
    ),
    OperatorCommand(
        name="nightly-schedule-preview",
        description="Preview Nightly schedule capability summary",
        category="nightly",
        dry_run_only=True,
    ),
    OperatorCommand(
        name="asset-dry-run",
        description="Run Asset dry-run adapter",
        category="asset",
        dry_run_only=True,
    ),
    OperatorCommand(
        name="rtcm-dry-run",
        description="Run RTCM roundtable dry-run",
        category="rtcm",
        dry_run_only=True,
    ),
]


def list_commands() -> list[OperatorCommand]:
    """Return all registered operator commands."""
    return list(_OPERATOR_COMMANDS)


def get_command(name: str) -> OperatorCommand | None:
    """Get a command by name, or None if not found."""
    for cmd in _OPERATOR_COMMANDS:
        if cmd.name == name:
            return cmd
    return None


def command_to_dict(cmd: OperatorCommand) -> dict[str, Any]:
    """Serialize a command to a dict."""
    return cmd.to_dict()


def result_to_dict(result: OperatorCommandResult) -> dict[str, Any]:
    """Serialize a result to a dict."""
    return result.to_dict()
