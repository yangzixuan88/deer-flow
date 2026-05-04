from pathlib import Path

import pytest

from app.nightly import foundation_health_review as fhr


def test_normalize_unknown_taxonomy_medium_refine_taxonomy():
    signal = fhr.normalize_health_signal(
        {"domain": "rtcm", "signal_type": "unknown_rtcm_runtime_surface", "message": "unknown"}
    )
    assert signal["severity"] == "medium"
    assert signal["recommended_action_type"] == "refine_taxonomy"


def test_normalize_missing_rollback_high():
    signal = fhr.normalize_health_signal(
        {"domain": "prompt", "signal_type": "rollback_missing", "message": "rollback missing"}
    )
    assert signal["severity"] == "high"
    assert signal["action_permission"] == "requires_rollback"


def test_create_action_candidate_low_report_only():
    signal = fhr.normalize_health_signal(
        {"domain": "mode", "severity": "low", "signal_type": "diagnostic", "message": "diag"}
    )
    action = fhr.create_action_candidate_from_signal(signal)
    assert action["permission"] == "report_only"
    assert action["auto_executable"] is False


def test_create_action_candidate_high_requires_protection():
    signal = fhr.normalize_health_signal(
        {
            "domain": "tool_runtime",
            "severity": "high",
            "signal_type": "missing_backup",
            "message": "backup missing",
        }
    )
    action = fhr.create_action_candidate_from_signal(signal)
    assert action["permission"] in {"requires_backup", "requires_user_confirmation"}
    assert action["auto_executable"] is False


def test_create_action_candidate_critical_forbidden_or_confirmation():
    signal = fhr.normalize_health_signal(
        {
            "domain": "asset",
            "severity": "critical",
            "signal_type": "asset_core_elimination_attempt",
            "message": "core elimination",
        }
    )
    action = fhr.create_action_candidate_from_signal(signal)
    assert action["permission"] in {"forbidden_auto", "requires_user_confirmation"}
    assert action["auto_executable"] is False


def test_collect_truth_state_health_monkeypatch_no_governance_write(monkeypatch):
    monkeypatch.setattr(
        fhr,
        "_safe_call",
        lambda func, domain, warnings, **kwargs: {
            "exists": False,
            "warnings": ["queue_missing"],
            "eligible_count": 0,
            "sandbox_records_count": 0,
        },
    )
    result = fhr.collect_truth_state_health()
    assert result["signals"]
    assert any(signal["domain"] in {"truth_state", "queue_sandbox"} for signal in result["signals"])


def test_collect_memory_health_monkeypatch_no_memory_write(monkeypatch):
    def fake_safe(func, domain, warnings, **kwargs):
        if "risk" in func.__name__:
            return {"risk_count": 1, "risk_by_type": {"checkpoint_not_long_term_memory": 1}, "warnings": []}
        return {"classified_count": 1, "candidate_count": 0, "warnings": []}

    monkeypatch.setattr(fhr, "_safe_call", fake_safe)
    result = fhr.collect_memory_health(root=str(Path.cwd()), max_files=1)
    assert result["summary"]["risk_count"] == 1


def test_collect_asset_health_monkeypatch_no_asset_write(monkeypatch):
    def fake_safe(func, domain, warnings, **kwargs):
        if "detect" in func.__name__:
            return {"risk_count": 1, "risk_by_type": {"missing_score_components": 1}, "warnings": []}
        return {"total_projected": 1, "candidate_count": 1, "formal_asset_count": 0, "warnings": []}

    monkeypatch.setattr(fhr, "_safe_call", fake_safe)
    result = fhr.collect_asset_health(limit=1)
    assert result["summary"]["candidate_count"] == 1


def test_collect_prompt_health_monkeypatch_no_prompt_write(monkeypatch):
    def fake_safe(func, domain, warnings, **kwargs):
        return {
            "source_projection": {"classified_count": 1},
            "asset_candidates": {"candidate_count": 1},
            "risk_signals": {"risk_count": 1, "risk_by_type": {"critical_prompt_without_rollback": 1}},
            "warnings": [],
        }

    monkeypatch.setattr(fhr, "_safe_call", fake_safe)
    result = fhr.collect_prompt_health(root=str(Path.cwd()), max_files=1)
    assert result["summary"]["risk_count"] == 1


def test_collect_rtcm_health_monkeypatch_no_rtcm_write(monkeypatch):
    def fake_safe(func, domain, warnings, **kwargs):
        if "detect" in func.__name__:
            return {"risk_count": 1, "risk_by_type": {"session_missing_context_link": 1}, "warnings": []}
        if "aggregate" in func.__name__:
            return {"truth_candidates": {"candidate_count": 1}, "warnings": []}
        return {
            "classified_count": 1,
            "unknown_count": 0,
            "session_count": 1,
            "truth_candidate_count": 1,
            "asset_candidate_count": 1,
            "memory_candidate_count": 1,
            "followup_candidate_count": 1,
            "warnings": [],
        }

    monkeypatch.setattr(fhr, "_safe_call", fake_safe)
    result = fhr.collect_rtcm_health(root=str(Path.cwd()), max_files=1)
    assert result["summary"]["session_count"] == 1


def test_collector_failure_becomes_warning_not_aggregate_break(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(fhr, "collect_memory_health", fail)
    monkeypatch.setattr(fhr, "collect_truth_state_health", lambda **kwargs: {"signals": [], "summary": {}, "warnings": []})
    monkeypatch.setattr(fhr, "collect_asset_health", lambda **kwargs: {"signals": [], "summary": {}, "warnings": []})
    monkeypatch.setattr(fhr, "collect_mode_health", lambda **kwargs: {"signals": [], "summary": {}, "warnings": []})
    monkeypatch.setattr(fhr, "collect_tool_runtime_health", lambda **kwargs: {"signals": [], "summary": {}, "warnings": []})
    monkeypatch.setattr(fhr, "collect_prompt_health", lambda **kwargs: {"signals": [], "summary": {}, "warnings": []})
    monkeypatch.setattr(fhr, "collect_rtcm_health", lambda **kwargs: {"signals": [], "summary": {}, "warnings": []})
    review = fhr.aggregate_nightly_foundation_health(root=str(Path.cwd()), max_files=1)
    assert review["warnings"]
    assert review["total_signals"] >= 1


def test_aggregate_nightly_foundation_health_multiple_domains(monkeypatch):
    collector_result = {
        "signals": [
            fhr.normalize_health_signal(
                {"domain": "memory", "signal_type": "unknown_memory_artifact", "message": "unknown"}
            )
        ],
        "summary": {"ok": True},
        "warnings": [],
    }
    for name in [
        "collect_truth_state_health",
        "collect_memory_health",
        "collect_asset_health",
        "collect_mode_health",
        "collect_tool_runtime_health",
        "collect_prompt_health",
        "collect_rtcm_health",
    ]:
        monkeypatch.setattr(fhr, name, lambda **kwargs: collector_result)
    review = fhr.aggregate_nightly_foundation_health(root=str(Path.cwd()), max_files=1)
    assert review["total_signals"] == 7
    assert review["action_candidate_count"] == 7


def test_generate_nightly_foundation_health_review_writes_only_tmp_path(tmp_path, monkeypatch):
    monkeypatch.setattr(
        fhr,
        "aggregate_nightly_foundation_health",
        lambda root=None, max_files=500: {
            "review_id": "r1",
            "warnings": [],
            "signals": [],
            "action_candidates": [],
        },
    )
    output = tmp_path / "review.json"
    result = fhr.generate_nightly_foundation_health_review(output_path=str(output), root=str(tmp_path), max_files=1)
    assert output.exists()
    assert result["output_path"] == str(output)


def test_no_real_action_queue_created(tmp_path):
    output = tmp_path / "review.json"
    fhr.generate_nightly_foundation_health_review(output_path=str(output), root=str(tmp_path), max_files=1)
    assert not (tmp_path / "action_queue.json").exists()


def test_does_not_execute_tools(monkeypatch):
    called = {"value": False}

    def fake_tool_sample(*args, **kwargs):
        called["value"] = True
        return {"events": [], "warnings": []}

    monkeypatch.setattr(fhr, "_safe_call", lambda func, domain, warnings, **kwargs: {"events": [], "warnings": []})
    fhr.collect_tool_runtime_health()
    assert called["value"] is False


def test_does_not_modify_runtime(tmp_path):
    before = set(tmp_path.iterdir())
    fhr.aggregate_nightly_foundation_health(root=str(tmp_path), max_files=1)
    after = set(tmp_path.iterdir())
    assert before == after


def test_high_risk_action_candidate_not_auto_executable():
    signal = fhr.normalize_health_signal(
        {"domain": "tool_runtime", "severity": "high", "signal_type": "level_3_requires_confirmation", "message": "confirm"}
    )
    action = fhr.create_action_candidate_from_signal(signal)
    assert action["auto_executable"] is False


@pytest.mark.parametrize(
    "signal_type",
    ["prompt_replace", "memory_cleanup", "asset_elimination"],
)
def test_high_risk_runtime_mutations_forbidden_auto(signal_type):
    signal = fhr.normalize_health_signal(
        {"domain": "prompt", "severity": "critical", "signal_type": signal_type, "message": signal_type}
    )
    action = fhr.create_action_candidate_from_signal(signal)
    assert action["permission"] == "forbidden_auto"

