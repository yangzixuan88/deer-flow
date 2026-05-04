"""Internal wrapper for read-only foundation diagnostics.

This script intentionally does not register a global CLI, does not expose HTTP,
and does not write runtime state.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
for path in (ROOT, BACKEND):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.foundation.read_only_diagnostics_cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
