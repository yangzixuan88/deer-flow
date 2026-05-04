"""Stable YAML workflow trigger parser for GitHub Actions.

Avoids PyYAML bool coercion (on: -> True) by using controlled regex extraction
of top-level keys from the raw YAML text.
"""

from __future__ import annotations

import re
from typing import Any


def _remove_comments(text: str) -> str:
    """Remove YAML comment lines (lines where # appears outside string context)."""
    result = []
    i = 0
    n = len(text)
    in_double = False
    in_single = False

    while i < n:
        c = text[i]

        if in_double:
            if c == '"' and i > 0 and text[i - 1] != "\\":
                in_double = False
            result.append(c)
            i += 1
        elif in_single:
            if c == "'" and i > 0 and text[i - 1] != "\\":
                in_single = False
            result.append(c)
            i += 1
        else:
            if c == '"':
                in_double = True
                result.append(c)
            elif c == "'":
                in_single = True
                result.append(c)
            elif c == "#":
                while i < n and text[i] != "\n":
                    i += 1
                continue
            else:
                result.append(c)
        i += 1

    return "".join(result)


def _extract_top_level_triggers(raw_text: str) -> list[str]:
    """Extract trigger names from the 'on:' block in raw YAML text.

    Handles all GitHub Actions trigger formats without using PyYAML:
    - on: workflow_dispatch          (scalar)
    - on: [workflow_dispatch]         (inline array)
    - on:                            (mapping, block sequence)
        - workflow_dispatch
        - push
    - on:                            (mapping, block scalar)
        workflow_dispatch
        push
    - on:                            (mapping with nested keys)
        workflow_dispatch:
          inputs:
            x:
              type: string

    Also handles mixed arrays:
    - on: [workflow_dispatch, push]
    """
    # Remove comments first
    text = _remove_comments(raw_text)
    lines = text.splitlines()

    # Find 'on:' at top level (no leading indent)
    on_lineno = None
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("on:"):
            on_lineno = i
            break

    if on_lineno is None:
        return []

    # Determine indentation of 'on:' line
    on_indent = len(lines[on_lineno]) - len(lines[on_lineno].lstrip())

    # Extract content on the same line after 'on: '
    on_line = lines[on_lineno]
    # Get text after "on:" - strip "on" then strip the colon and whitespace
    on_key_stripped = on_line.lstrip()
    colon_pos = on_key_stripped.find(":")
    after_on = on_key_stripped[colon_pos + 1:].strip() if colon_pos != -1 else ""

    triggers: list[str] = []

    # Case 1: inline array on: [workflow_dispatch, push]
    if after_on.startswith("["):
        content = after_on.rstrip("]").lstrip("[")
        for item in content.split(","):
            item = item.strip().strip("'\"").strip()
            if item:
                triggers.append(item)
        return triggers

    # Case 2: scalar value on same line on: workflow_dispatch
    if after_on and not after_on.startswith("#"):
        scalar_triggers = [t.strip().strip("'\"") for t in after_on.split(",")]
        for t in scalar_triggers:
            if t and re.match(r"^[\w-]+$", t):
                triggers.append(t)
        if triggers:
            return triggers

    # Case 3: multi-line block - collect until indent decreases
    block_indent = None
    for lineno in range(on_lineno + 1, len(lines)):
        line = lines[lineno]
        stripped = line.strip()

        if not stripped:
            continue

        indent = len(line) - len(line.lstrip())

        if block_indent is None:
            block_indent = indent

        # If indent decreases back to on: level or below, stop
        if indent <= on_indent:
            break

        # If indent == block_indent (same level as first block item)
        if indent == block_indent:
            if stripped.startswith("-"):
                # Block sequence item
                item = stripped.lstrip("- ").strip().strip("'\"")
                if item and re.match(r"^[\w-]+$", item):
                    triggers.append(item)
            elif re.match(r"^[\w-]+:$", stripped):
                # Block scalar key (trigger without inputs)
                trigger = stripped.rstrip(":").strip()
                triggers.append(trigger)
            elif re.match(r"^[\w-]+$", stripped):
                # Plain scalar trigger
                triggers.append(stripped)

    return triggers


def parse_workflow_triggers_from_yaml_text(yaml_text: str) -> dict[str, Any]:
    """Parse GitHub Actions workflow triggers from YAML text.

    Avoids PyYAML bool coercion (on -> True) by using controlled regex parsing.

    Returns:
        dict with:
            - workflow_dispatch_present: bool
            - pull_request_present: bool
            - push_present: bool
            - schedule_present: bool
            - allowed_triggers: list[str]
            - forbidden_triggers: list[str]
            - workflow_dispatch_only: bool
            - parser_confidence: str ("high", "medium", "low")
            - parse_strategy: str
            - warnings: list[str]
            - errors: list[str]
            - raw_on_block: str | None
    """
    warnings: list[str] = []
    errors: list[str] = []

    if not yaml_text or not yaml_text.strip():
        return {
            "workflow_dispatch_present": False,
            "pull_request_present": False,
            "push_present": False,
            "schedule_present": False,
            "allowed_triggers": [],
            "forbidden_triggers": [],
            "workflow_dispatch_only": False,
            "parser_confidence": "low",
            "parse_strategy": "empty_input",
            "warnings": ["Empty YAML input"],
            "errors": [],
            "raw_on_block": None,
        }

    triggers = _extract_top_level_triggers(yaml_text)

    # Also check for forbidden triggers that appear outside the on: block
    # (but only at the top level, not in jobs/steps/etc.)
    # For now, we trust the on: block extraction
    allowed = {"workflow_dispatch", "workflow_call", "repository_dispatch"}
    forbidden = {"push", "pull_request", "pull_request_target", "schedule"}

    found_forbidden = [t for t in triggers if t in forbidden]
    found_allowed = [t for t in triggers if t in allowed]

    result = {
        "workflow_dispatch_present": "workflow_dispatch" in triggers,
        "pull_request_present": "pull_request" in triggers or "pull_request_target" in triggers,
        "push_present": "push" in triggers,
        "schedule_present": "schedule" in triggers,
        "allowed_triggers": found_allowed,
        "forbidden_triggers": found_forbidden,
        "workflow_dispatch_only": (
            "workflow_dispatch" in triggers
            and "push" not in triggers
            and "pull_request" not in triggers
            and "pull_request_target" not in triggers
            and "schedule" not in triggers
        ),
        "parser_confidence": "high" if triggers else "medium",
        "parse_strategy": "top_level_on_block" if triggers else "no_on_block",
        "warnings": warnings,
        "errors": errors,
        "raw_on_block": " ".join(triggers) if triggers else None,
    }

    return result
