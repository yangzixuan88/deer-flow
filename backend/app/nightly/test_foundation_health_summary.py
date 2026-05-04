import json
from pathlib import Path

from app.nightly import foundation_health_summary as fhs


def _review():
    return {
        "review_id": "review-1",
        "generated_at": "2026-04-25T00:00:00Z",
        "total_signals": 4,
        "by_severity": {"critical": 1, "high": 2, "medium": 1},
        "critical_count": 1,
        "high_count": 2,
        "action_candidate_count": 4,
        "requires_confirmation_count": 2,
        "blocked_high_risk_count": 1,
        "signals": [
            {"signal_id": "s1", "domain": "prompt", "severity": "critical", "signal_type": "critical_prompt_without_rollback", "message": "prompt rollback missing", "recommended_action_type": "add_rollback"},
            {"signal_id": "s2", "domain": "tool_runtime", "severity": "high", "signal_type": "level_3_requires_confirmation", "message": "confirm tool", "recommended_action_type": "requires_user_confirmation"},
            {"signal_id": "s3", "domain": "rtcm", "severity": "high", "signal_type": "unknown_rtcm_runtime_surface", "message": "unknown rtcm", "recommended_action_type": "refine_taxonomy"},
            {"signal_id": "s4", "domain": "memory", "severity": "medium", "signal_type": "unknown_memory_artifact", "message": "unknown memory", "recommended_action_type": "refine_taxonomy"},
        ],
        "action_candidates": [
            {"action_candidate_id": "a1", "domain": "prompt", "severity": "critical", "permission": "forbidden_auto", "title": "prompt rollback", "action_type": "add_rollback", "auto_executable": False, "requires_user_confirmation": True, "blocked_reason": "forbidden"},
            {"action_candidate_id": "a2", "domain": "tool_runtime", "severity": "high", "permission": "requires_user_confirmation", "title": "tool confirmation", "action_type": "requires_user_confirmation", "auto_executable": False, "requires_user_confirmation": True},
            {"action_candidate_id": "a3", "domain": "rtcm", "severity": "high", "permission": "report_only", "title": "rtcm taxonomy", "action_type": "refine_taxonomy", "auto_executable": False, "requires_user_confirmation": False},
            {"action_candidate_id": "a4", "domain": "memory", "severity": "medium", "permission": "report_only", "title": "memory taxonomy", "action_type": "refine_taxonomy", "auto_executable": False, "requires_user_confirmation": False},
        ],
        "warnings": [],
    }


def test_load_latest_nightly_review_sample_missing_file_warning(tmp_path):
    result = fhs.load_latest_nightly_review_sample(str(tmp_path / "missing.json"))
    assert result["exists"] is False
    assert result["warnings"]


def test_load_latest_nightly_review_sample_malformed_json_warning(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{bad", encoding="utf-8")
    result = fhs.load_latest_nightly_review_sample(str(p))
    assert result["exists"] is True
    assert result["warnings"]


def test_summarize_review_for_user_counts():
    summary = fhs.summarize_review_for_user(_review())
    assert summary["critical_count"] == 1
    assert summary["high_count"] == 2
    assert summary["action_candidate_count"] == 4
    assert "projection" in summary["headline"]


def test_summarize_review_by_domain_counts():
    result = fhs.summarize_review_by_domain(_review())
    prompt = next(row for row in result["domains"] if row["domain"] == "prompt")
    assert prompt["critical_count"] == 1
    assert prompt["signal_count"] == 1


def test_select_top_action_candidates_critical_first():
    result = fhs.select_top_action_candidates(_review(), max_items=2)
    assert result["actions"][0]["severity"] == "critical"


def test_select_top_action_candidates_forbidden_confirmation_priority():
    result = fhs.select_top_action_candidates(_review(), max_items=2)
    permissions = [item["permission"] for item in result["actions"]]
    assert permissions[0] == "forbidden_auto"
    assert "requires_user_confirmation" in permissions


def test_build_feishu_card_payload_projection_send_false():
    payload = fhs.build_feishu_card_payload_projection(_review())
    assert payload["send_allowed"] is False
    assert payload["webhook_required"] is True


def test_build_feishu_card_payload_projection_status_projection_only():
    payload = fhs.build_feishu_card_payload_projection(_review())
    assert payload["status"] == "projection_only"


def test_build_feishu_card_payload_projection_no_webhook_call():
    payload = fhs.build_feishu_card_payload_projection(_review())
    assert payload["no_webhook_call"] is True


def test_build_plaintext_nightly_summary_chinese():
    result = fhs.build_plaintext_nightly_summary(_review())
    assert "摘要" in result["text"]
    assert "不会推送 Feishu" in result["text"]


def test_validate_feishu_payload_projection_valid():
    payload = fhs.build_feishu_card_payload_projection(_review())
    validation = fhs.validate_feishu_payload_projection(payload)
    assert validation["valid"] is True


def test_generate_nightly_summary_projection_report_writes_only_tmp_path(tmp_path):
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps({"review": _review()}, ensure_ascii=False), encoding="utf-8")
    output = tmp_path / "summary.json"
    result = fhs.generate_nightly_summary_projection_report(output_path=str(output), review_path=str(review_path))
    assert output.exists()
    assert result["output_path"] == str(output)


def test_does_not_create_real_action_queue(tmp_path):
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps({"review": _review()}, ensure_ascii=False), encoding="utf-8")
    fhs.generate_nightly_summary_projection_report(output_path=str(tmp_path / "summary.json"), review_path=str(review_path))
    assert not (tmp_path / "action_queue.json").exists()


def test_does_not_call_feishu_webhook(monkeypatch):
    called = {"value": False}

    def fake_post(*args, **kwargs):
        called["value"] = True

    monkeypatch.setattr("urllib.request.urlopen", fake_post)
    payload = fhs.build_feishu_card_payload_projection(_review())
    assert payload["send_allowed"] is False
    assert called["value"] is False


def test_does_not_execute_auto_fix(tmp_path):
    before = set(tmp_path.iterdir())
    fhs.build_plaintext_nightly_summary(_review())
    after = set(tmp_path.iterdir())
    assert before == after


def test_malformed_review_does_not_crash():
    summary = fhs.summarize_review_for_user(["bad"])
    assert summary["warnings"]
    payload = fhs.build_feishu_card_payload_projection(["bad"])
    assert payload["send_allowed"] is False

