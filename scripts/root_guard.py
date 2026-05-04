#!/usr/bin/env python3
"""
root_guard.py
R240: Enforce the single valid development root.
"""
from __future__ import annotations

import sys
from pathlib import Path


def _old_root_name() -> str:
    return "openclaw" + "".join(chr(code) for code in (0x8D85, 0x7EA7, 0x5DE5, 0x7A0B, 0x9879, 0x76EE))


def _normalize(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return Path(str(path))


def _is_same_or_child(current: Path, root: Path) -> bool:
    current_norm = _normalize(current)
    root_norm = _normalize(root)
    try:
        return current_norm == root_norm or root_norm in current_norm.parents
    except (ValueError, OSError):
        current_text = str(current_norm).rstrip("\\/").casefold()
        root_text = str(root_norm).rstrip("\\/").casefold()
        return current_text == root_text or current_text.startswith(root_text + "\\")


def check_root_guard() -> bool:
    """
    Returns True if root is correct.
    Returns False if root is forbidden or incorrect.
    """
    expected_root = Path(r"E:\OpenClaw-Base\deerflow")
    old_name = _old_root_name()
    forbidden_roots = (
        Path(r"E:\OpenClaw-Base") / old_name,
        Path(r"E:\OpenClaw-Base") / f"{old_name}__MIGRATED_DO_NOT_USE",
    )

    try:
        cwd = Path.cwd()
    except Exception:
        print("[RootGuard] ERROR: Cannot determine current directory", file=sys.stderr)
        return False

    if any(_is_same_or_child(cwd, forbidden_root) for forbidden_root in forbidden_roots):
        print("[RootGuard] FORBIDDEN: You are inside the migrated old directory.", file=sys.stderr)
        print(f"[RootGuard] Expected root: {expected_root}", file=sys.stderr)
        print(f"[RootGuard] Please open: {expected_root}\\OpenClaw-DeerFlow.code-workspace", file=sys.stderr)
        return False

    if not _is_same_or_child(cwd, expected_root):
        print("[RootGuard] WARNING: Current directory is outside expected root.", file=sys.stderr)
        print(f"[RootGuard] Expected root: {expected_root}", file=sys.stderr)
        print(f"[RootGuard] Current: {cwd}", file=sys.stderr)
        print(f"[RootGuard] Please switch to: {expected_root}", file=sys.stderr)
        return False

    print(f"[RootGuard] ROOT_OK ({expected_root})")
    return True


if __name__ == "__main__":
    ok = check_root_guard()
    sys.exit(0 if ok else 1)
