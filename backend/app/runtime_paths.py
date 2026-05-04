"""Project-local DeerFlow runtime paths."""

from __future__ import annotations

import os
from pathlib import Path

DEERFLOW_ROOT = Path(os.environ.get("DEERFLOW_ROOT", Path(__file__).resolve().parents[2])).resolve()
DEERFLOW_RUNTIME_ROOT = Path(os.environ.get("DEERFLOW_RUNTIME_ROOT", DEERFLOW_ROOT / ".deerflow")).resolve()


def runtime_path(*parts: str) -> Path:
    return DEERFLOW_RUNTIME_ROOT.joinpath(*parts)


def upgrade_center_state_dir() -> Path:
    return runtime_path("upgrade-center", "state")
