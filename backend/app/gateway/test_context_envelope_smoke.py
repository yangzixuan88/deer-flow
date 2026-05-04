"""
R240-4 ContextEnvelope Smoke Tests
===================================
验证所有 R240-4 实现组件的基本功能。
"""

import asyncio
import sys
import uuid

sys.path.insert(0, ".")


def test_context_envelope_creation():
    """Test 1: ContextEnvelope can be created with default fields."""
    from app.gateway.context import ContextEnvelope, generate_context_id

    env = ContextEnvelope(source_system="gateway", owner_system="gateway")
    assert env.context_id is not None
    assert len(env.context_id) == 36  # UUID format
    assert env.request_id is not None
    assert env.source_system == "gateway"
    assert env.owner_system == "gateway"
    print("  [PASS] test_context_envelope_creation")


def test_context_envelope_from_dict():
    """Test 2: ContextEnvelope.from_dict handles existing envelope."""
    from app.gateway.context import ContextEnvelope, ensure_context_envelope

    payload = {
        "context_envelope": {
            "context_id": "existing-ctx-id",
            "request_id": "existing-req-id",
        }
    }
    env = ensure_context_envelope(payload, "gateway", "gateway")
    assert env.context_id == "existing-ctx-id"
    assert env.request_id == "existing-req-id"
    print("  [PASS] test_context_envelope_from_dict")


def test_context_envelope_to_dict():
    """Test 3: ContextEnvelope.to_dict round-trips correctly."""
    from app.gateway.context import ContextEnvelope

    env = ContextEnvelope(context_id="test-ctx", request_id="test-req", thread_id="test-thread")
    d = env.to_dict()
    assert d["context_id"] == "test-ctx"
    assert d["request_id"] == "test-req"
    assert d["thread_id"] == "test-thread"
    assert d["source_system"] == "gateway"
    print("  [PASS] test_context_envelope_to_dict")


def test_inject_and_extract():
    """Test 4: inject_envelope_into_context / extract_envelope_from_context round-trip."""
    from app.gateway.context import (
        ContextEnvelope,
        inject_envelope_into_context,
        extract_envelope_from_context,
    )

    env = ContextEnvelope(source_system="gateway", owner_system="gateway")
    ctx = {}
    inject_envelope_into_context(ctx, env)
    assert "context_envelope" in ctx

    extracted = extract_envelope_from_context(ctx)
    assert extracted is not None
    assert extracted.context_id == env.context_id
    assert extracted.request_id == env.request_id
    print("  [PASS] test_inject_and_extract")


def test_context_link_creation():
    """Test 5: ContextLink can be created and appended to jsonl."""
    from app.gateway.context import ContextLink, RelationType, append_context_link

    link = ContextLink(
        from_context_id="thread-abc",
        to_context_id="session-def",
        relation_type=RelationType.BELONGS_TO_SESSION,
        source_system="gateway",
    )
    assert link.link_id is not None
    assert link.relation_type == "belongs_to_session"

    # Append should not raise (non-fatal)
    result = append_context_link(link)
    assert result is True
    print("  [PASS] test_context_link_creation")


def test_services_module_imports():
    """Test 6: services.py imports all R240-4 context symbols."""
    from app.gateway import services
    from app.gateway.context import (
        ContextEnvelope,
        ContextLink,
        RelationType,
        append_context_link,
        ensure_context_envelope,
        envelope_summary,
        extract_envelope_from_context,
        inject_envelope_into_context,
    )

    # Verify services imports context module symbols
    assert hasattr(services, "ContextEnvelope")
    assert hasattr(services, "ContextLink")
    assert hasattr(services, "RelationType")
    assert hasattr(services, "append_context_link")
    assert hasattr(services, "ensure_context_envelope")
    assert hasattr(services, "envelope_summary")
    assert hasattr(services, "extract_envelope_from_context")
    assert hasattr(services, "inject_envelope_into_context")
    print("  [PASS] test_services_module_imports")


def test_build_run_config_no_breakage():
    """Test 7: build_run_config still works (no regression)."""
    from app.gateway.services import build_run_config

    config = build_run_config(
        thread_id="test-thread",
        request_config=None,
        metadata={"key": "value"},
        assistant_id=None,
    )
    assert config["configurable"]["thread_id"] == "test-thread"
    assert config["recursion_limit"] == 100
    assert config["metadata"]["key"] == "value"
    print("  [PASS] test_build_run_config_no_breakage")


def test_normalize_stream_modes():
    """Test 8: normalize_stream_modes still works (no regression)."""
    from app.gateway.services import normalize_stream_modes

    assert normalize_stream_modes(None) == ["values"]
    assert normalize_stream_modes("messages") == ["messages"]
    assert normalize_stream_modes(["values", "updates"]) == ["values", "updates"]
    print("  [PASS] test_normalize_stream_modes")


def test_normalize_input():
    """Test 9: normalize_input still works (no regression)."""
    from app.gateway.services import normalize_input

    result = normalize_input({"messages": [{"role": "user", "content": "hello"}]})
    from langchain_core.messages import HumanMessage

    assert len(result["messages"]) == 1
    assert isinstance(result["messages"][0], HumanMessage)
    print("  [PASS] test_normalize_input")


def test_format_sse():
    """Test 10: format_sse still works (no regression)."""
    from app.gateway.services import format_sse

    frame = format_sse("message", {"content": "hello"}, event_id="123")
    assert "event: message" in frame
    assert '"content": "hello"' in frame
    assert "id: 123" in frame
    print("  [PASS] test_format_sse")


def test_envelope_summary_no_sensitive_leak():
    """Test 11: envelope_summary masks full IDs (shows only first 8 chars + ...)."""
    from app.gateway.context import ContextEnvelope, envelope_summary

    env = ContextEnvelope(
        context_id="12345678-1234-1234-1234-123456789abc",
        request_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    )
    summary = envelope_summary(env)
    # Masked form is "12345678..." — full 36-char UUID must not appear
    assert "12345678-1234-1234-1234-123456789abc" not in summary
    assert "12345678..." in summary  # masked form present
    assert "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" not in summary
    assert "aaaaaaaa..." in summary
    print("  [PASS] test_envelope_summary_no_sensitive_leak")


def main():
    print("\n=== R240-4 ContextEnvelope Smoke Tests ===\n")

    tests = [
        test_context_envelope_creation,
        test_context_envelope_from_dict,
        test_context_envelope_to_dict,
        test_inject_and_extract,
        test_context_link_creation,
        test_services_module_imports,
        test_build_run_config_no_breakage,
        test_normalize_stream_modes,
        test_normalize_input,
        test_format_sse,
        test_envelope_summary_no_sensitive_leak,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {test.__name__}: {e}")
            failed += 1

    print(f"\n{'='*44}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("ALL SMOKE TESTS PASSED")
    else:
        print("SOME SMOKE TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
