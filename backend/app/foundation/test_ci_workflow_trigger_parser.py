"""Tests for ci_workflow_trigger_parser.py."""

from __future__ import annotations

import pytest
from backend.app.foundation.ci_workflow_trigger_parser import (
    parse_workflow_triggers_from_yaml_text,
)


class TestParseWorkflowTriggers:
    def test_on_mapping_workflow_dispatch_only(self):
        yaml_text = """name: Foundation Manual Dispatch
on:
  workflow_dispatch:
    inputs:
      confirm_manual_dispatch:
        description: "Must be: CONFIRM"
        required: true
        type: string
permissions:
  contents: read
jobs:
  job_smoke:
    runs-on: ubuntu-latest
    steps:
      - run: echo hello
"""
        result = parse_workflow_triggers_from_yaml_text(yaml_text)
        assert result["workflow_dispatch_present"] is True
        assert result["pull_request_present"] is False
        assert result["push_present"] is False
        assert result["schedule_present"] is False
        assert result["workflow_dispatch_only"] is True
        assert result["parser_confidence"] == "high"

    def test_on_scalar_workflow_dispatch_only(self):
        yaml_text = "on: workflow_dispatch\nname: Test"
        result = parse_workflow_triggers_from_yaml_text(yaml_text)
        assert result["workflow_dispatch_present"] is True
        assert result["pull_request_present"] is False
        assert result["push_present"] is False
        assert result["schedule_present"] is False
        assert result["workflow_dispatch_only"] is True

    def test_on_inline_array_workflow_dispatch_only(self):
        yaml_text = "on: [workflow_dispatch]\nname: Test"
        result = parse_workflow_triggers_from_yaml_text(yaml_text)
        assert result["workflow_dispatch_present"] is True
        assert result["workflow_dispatch_only"] is True

    def test_on_block_sequence_workflow_dispatch_only(self):
        yaml_text = "on:\n  - workflow_dispatch\nname: Test"
        result = parse_workflow_triggers_from_yaml_text(yaml_text)
        assert result["workflow_dispatch_present"] is True
        assert result["workflow_dispatch_only"] is True

    def test_workflow_dispatch_with_inputs(self):
        yaml_text = """on:
  workflow_dispatch:
    inputs:
      stage_selection:
        description: Stage
        required: false
        default: all_pr
        type: string
"""
        result = parse_workflow_triggers_from_yaml_text(yaml_text)
        assert result["workflow_dispatch_present"] is True
        assert result["workflow_dispatch_only"] is True

    def test_push_trigger_detected(self):
        yaml_text = "on: push\nname: Test"
        result = parse_workflow_triggers_from_yaml_text(yaml_text)
        assert result["push_present"] is True
        assert result["workflow_dispatch_only"] is False

    def test_pull_request_trigger_detected(self):
        yaml_text = "on: pull_request\nname: Test"
        result = parse_workflow_triggers_from_yaml_text(yaml_text)
        assert result["pull_request_present"] is True
        assert result["workflow_dispatch_only"] is False

    def test_schedule_trigger_detected(self):
        yaml_text = "on: schedule\n  cron: '0 0 * * *'\nname: Test"
        result = parse_workflow_triggers_from_yaml_text(yaml_text)
        assert result["schedule_present"] is True
        assert result["workflow_dispatch_only"] is False

    def test_inline_array_with_push_blocks(self):
        yaml_text = "on: [push, workflow_dispatch]\nname: Test"
        result = parse_workflow_triggers_from_yaml_text(yaml_text)
        assert result["push_present"] is True
        assert result["workflow_dispatch_present"] is True
        assert result["workflow_dispatch_only"] is False

    def test_block_sequence_with_push_blocks(self):
        yaml_text = "on:\n  - push\n  - workflow_dispatch\nname: Test"
        result = parse_workflow_triggers_from_yaml_text(yaml_text)
        assert result["push_present"] is True
        assert result["workflow_dispatch_present"] is True
        assert result["workflow_dispatch_only"] is False

    def test_comments_containing_push_do_not_trigger(self):
        yaml_text = """# This workflow has push but only in comments
# on: push
on: workflow_dispatch
name: Test
"""
        result = parse_workflow_triggers_from_yaml_text(yaml_text)
        assert result["push_present"] is False
        assert result["workflow_dispatch_present"] is True
        assert result["workflow_dispatch_only"] is True

    def test_script_text_containing_push_do_not_trigger(self):
        yaml_text = """on: workflow_dispatch
jobs:
  test:
    runs-on: ubuntu
    steps:
      - run: git push origin main
"""
        result = parse_workflow_triggers_from_yaml_text(yaml_text)
        assert result["push_present"] is False
        assert result["workflow_dispatch_present"] is True

    def test_job_name_containing_schedule_do_not_trigger(self):
        yaml_text = """on: workflow_dispatch
jobs:
  scheduled_task:
    runs-on: ubuntu
    steps:
      - run: echo hello
"""
        result = parse_workflow_triggers_from_yaml_text(yaml_text)
        assert result["schedule_present"] is False
        assert result["workflow_dispatch_present"] is True

    def test_yaml_without_on_returns_no_triggers(self):
        yaml_text = """name: Test
jobs:
  build:
    runs-on: ubuntu
"""
        result = parse_workflow_triggers_from_yaml_text(yaml_text)
        assert result["workflow_dispatch_present"] is False
        assert result["workflow_dispatch_only"] is False
        assert result["parser_confidence"] == "medium"
        assert len(result["allowed_triggers"]) == 0

    def test_empty_yaml_returns_no_triggers_with_warning(self):
        yaml_text = ""
        result = parse_workflow_triggers_from_yaml_text(yaml_text)
        assert result["workflow_dispatch_present"] is False
        assert result["parser_confidence"] == "low"
        assert len(result["warnings"]) > 0

    def test_pyyaml_bool_trap_avoided(self):
        yaml_text = """# Test with on: as boolean-like value
on: workflow_dispatch
permissions:
  contents: read
jobs:
  test:
    if: on == true
    runs-on: ubuntu
"""
        result = parse_workflow_triggers_from_yaml_text(yaml_text)
        assert result["workflow_dispatch_present"] is True
        assert result["workflow_dispatch_only"] is True
        assert result["parser_confidence"] == "high"

    def test_workflow_with_push_and_pr_and_schedule_not_dispatch_only(self):
        yaml_text = """on:
  push:
  pull_request:
  schedule:
    cron: '0 0 * * *'
"""
        result = parse_workflow_triggers_from_yaml_text(yaml_text)
        assert result["push_present"] is True
        assert result["pull_request_present"] is True
        assert result["schedule_present"] is True
        assert result["workflow_dispatch_present"] is False
        assert result["workflow_dispatch_only"] is False

    def test_workflow_with_multiple_allowed_and_no_forbidden(self):
        yaml_text = """on:
  workflow_dispatch:
  workflow_call:
"""
        result = parse_workflow_triggers_from_yaml_text(yaml_text)
        assert result["workflow_dispatch_present"] is True
        assert result["workflow_dispatch_only"] is True
        assert "workflow_call" in result["allowed_triggers"]

    def test_raw_on_block_returned(self):
        yaml_text = """on:
  workflow_dispatch:
    inputs:
      x:
        type: string
"""
        result = parse_workflow_triggers_from_yaml_text(yaml_text)
        assert result["raw_on_block"] is not None

    def test_workflow_call_trigger(self):
        yaml_text = "on: workflow_call\nname: Test"
        result = parse_workflow_triggers_from_yaml_text(yaml_text)
        assert result["workflow_dispatch_present"] is False
        assert result["workflow_dispatch_only"] is False
        assert "workflow_call" in result["allowed_triggers"]
        assert len(result["forbidden_triggers"]) == 0

    def test_repository_dispatch_trigger(self):
        yaml_text = "on: repository_dispatch\nname: Test"
        result = parse_workflow_triggers_from_yaml_text(yaml_text)
        assert result["workflow_dispatch_present"] is False
        assert "repository_dispatch" in result["allowed_triggers"]
        assert result["workflow_dispatch_only"] is False
        assert len(result["forbidden_triggers"]) == 0

    def test_no_forbidden_triggers(self):
        yaml_text = "on: workflow_dispatch\nname: Test"
        result = parse_workflow_triggers_from_yaml_text(yaml_text)
        assert len(result["forbidden_triggers"]) == 0
