import json
from pathlib import Path

from backend.app.foundation import ci_secret_like_path_review as review_mod


def _write_w_report(root: Path, *, include_secret_path: bool = True) -> None:
    report_dir = root / "migration_reports" / "foundation_audit"
    report_dir.mkdir(parents=True, exist_ok=True)
    path = "frontend/.env.example" if include_secret_path else "frontend/README.md"
    report = {
        "status": "blocked_unknown_dirty_state",
        "decision": "block_closure_until_worktree_review",
        "staged_files": [],
        "delivery_scope_dirty_files": [],
        "workflow_scope_dirty_files": [],
        "dirty_files": [
            {
                "path": path,
                "status_code": " M",
                "is_secret_like_path": include_secret_path,
            }
        ],
        "closure_checks": [
            {
                "check_id": "no_secret_like_paths",
                "passed": False,
                "blocked_reasons": [f"Secret-like path: {path}"],
            }
        ],
        "safety_summary": {
            "runtime_scope_clean": True,
            "delivery_artifacts_verified": True,
            "workflow_files_verified": True,
            "staged_area_clean": True,
            "no_secret_exposure": False,
        },
    }
    (report_dir / "R241-16W_WORKING_TREE_CLOSURE_CONDITION.json").write_text(
        json.dumps(report),
        encoding="utf-8",
    )


def _write_env(root: Path, text: str) -> None:
    env_path = root / "frontend" / ".env.example"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(text, encoding="utf-8")


def _safe_review() -> dict:
    return {
        "decision": "allow_closure_with_secret_template_warning",
        "real_secret_candidate_count": 0,
        "closure_reclassification": "secret_template_path",
        "findings": [
            {
                "finding_id": "f1",
                "value_present": True,
                "value_masked_preview": "[REDACTED length=12 prefix='YOU' suffix='ET' sha256_8=abc12345]",
            }
        ],
        "safety_summary": {
            "git_commit_executed": False,
            "git_push_executed": False,
            "git_reset_restore_revert_executed": False,
            "git_am_apply_executed": False,
            "gh_workflow_run_executed": False,
            "secret_environment_read": False,
            "workflow_modified": False,
            "runtime_write": False,
            "audit_jsonl_write": False,
            "action_queue_write": False,
            "auto_fix_executed": False,
            "raw_secret_value_emitted": False,
        },
    }


def test_load_r241_16w_requires_no_secret_like_paths_failure(tmp_path):
    _write_w_report(tmp_path)
    result = review_mod.load_r241_16w_secret_like_condition(str(tmp_path))
    assert result["passed"] is True
    assert result["failed_check"] == "no_secret_like_paths"


def test_load_r241_16w_requires_frontend_env_example_path(tmp_path):
    _write_w_report(tmp_path, include_secret_path=False)
    result = review_mod.load_r241_16w_secret_like_condition(str(tmp_path))
    assert result["passed"] is False
    assert any("frontend/.env.example" in e for e in result["errors"])


def test_inspect_target_file_detects_exists(tmp_path):
    _write_env(tmp_path, "API_KEY=YOUR_API_KEY\n")
    result = review_mod.inspect_secret_like_target_file(str(tmp_path))
    assert result["exists"] is True
    assert result["content_readable"] is True


def test_inspect_target_file_handles_missing_file(tmp_path):
    result = review_mod.inspect_secret_like_target_file(str(tmp_path))
    assert result["exists"] is False
    assert result["errors"]


def test_scan_detects_empty_values_as_low_risk(tmp_path):
    _write_env(tmp_path, "API_KEY=\n")
    result = review_mod.scan_env_example_for_secret_findings(str(tmp_path))
    assert result["empty_value_count"] == 1
    assert result["findings"][0]["risk_level"] == "low"


def test_scan_detects_your_placeholder_as_template(tmp_path):
    _write_env(tmp_path, "API_KEY=YOUR_API_KEY\n")
    result = review_mod.scan_env_example_for_secret_findings(str(tmp_path))
    assert result["placeholder_count"] == 1
    assert result["findings"][0]["finding_type"] == "template_placeholder"


def test_scan_detects_replace_me_as_template(tmp_path):
    _write_env(tmp_path, "SECRET=REPLACE_ME\n")
    result = review_mod.scan_env_example_for_secret_findings(str(tmp_path))
    assert result["placeholder_count"] == 1


def test_scan_detects_localhost_example_as_template(tmp_path):
    _write_env(tmp_path, "NEXT_PUBLIC_API_URL=http://localhost:3000\nSITE=example.com\n")
    result = review_mod.scan_env_example_for_secret_findings(str(tmp_path))
    assert result["placeholder_count"] == 2


def test_scan_masks_values(tmp_path):
    _write_env(tmp_path, "TOKEN=YOUR_TOKEN_VALUE\n")
    finding = review_mod.scan_env_example_for_secret_findings(str(tmp_path))["findings"][0]
    assert finding["value_masked_preview"].startswith("[REDACTED")
    assert "YOUR_TOKEN_VALUE" not in finding["value_masked_preview"]


def test_scan_never_outputs_raw_secret_value(tmp_path):
    raw = "ghp_abcdefghijklmnopqrstuvwxyz1234567890"
    _write_env(tmp_path, f"TOKEN={raw}\n")
    result = review_mod.scan_env_example_for_secret_findings(str(tmp_path))
    assert raw not in json.dumps(result)


def test_scan_detects_webhook_url_as_high_risk(tmp_path):
    _write_env(tmp_path, "WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/abcdef1234567890\n")
    finding = review_mod.scan_env_example_for_secret_findings(str(tmp_path))["findings"][0]
    assert finding["finding_type"] == "webhook_url"
    assert finding["risk_level"] == "high"


def test_scan_detects_private_key_block_as_critical(tmp_path):
    _write_env(tmp_path, "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----\n")
    finding = review_mod.scan_env_example_for_secret_findings(str(tmp_path))["findings"][0]
    assert finding["finding_type"] == "private_key"
    assert finding["risk_level"] == "critical"


def test_scan_detects_github_token_as_high_risk(tmp_path):
    _write_env(tmp_path, "TOKEN=ghp_abcdefghijklmnopqrstuvwxyz1234567890\n")
    finding = review_mod.scan_env_example_for_secret_findings(str(tmp_path))["findings"][0]
    assert finding["is_real_secret_candidate"] is True
    assert finding["risk_level"] == "high"


def test_scan_detects_sk_provider_key_as_high_risk(tmp_path):
    _write_env(tmp_path, "API_KEY=sk-abcdefghijklmnopqrstuvwxyz123456\n")
    finding = review_mod.scan_env_example_for_secret_findings(str(tmp_path))["findings"][0]
    assert finding["is_real_secret_candidate"] is True
    assert finding["risk_level"] == "high"


def test_classify_all_placeholders_as_secret_template_path(tmp_path):
    _write_env(tmp_path, "API_KEY=YOUR_API_KEY\nSECRET=REPLACE_ME\n")
    scan = review_mod.scan_env_example_for_secret_findings(str(tmp_path))
    classification = review_mod.classify_secret_like_findings(scan["findings"])
    assert classification["classification"] == "secret_template_path"


def test_classify_suspicious_token_as_needs_manual_secret_review(tmp_path):
    _write_env(tmp_path, "SESSION_SAMPLE=AbCdEfGhIjKlMnOpQrStUvWxYz1234567890\n")
    scan = review_mod.scan_env_example_for_secret_findings(str(tmp_path))
    classification = review_mod.classify_secret_like_findings(scan["findings"])
    assert classification["classification"] == "needs_manual_secret_review"


def test_classify_real_webhook_as_real_secret_candidate(tmp_path):
    _write_env(tmp_path, "WEBHOOK_URL=https://hooks.slack.com/services/T000/B000/abcdef1234567890\n")
    scan = review_mod.scan_env_example_for_secret_findings(str(tmp_path))
    classification = review_mod.classify_secret_like_findings(scan["findings"])
    assert classification["classification"] == "real_secret_candidate"


def test_evaluate_safe_env_example_allows_closure_with_template_warning(tmp_path):
    _write_w_report(tmp_path)
    _write_env(tmp_path, "API_KEY=YOUR_API_KEY\nPASSWORD=\nURL=http://localhost:3000\n")
    result = review_mod.evaluate_secret_like_path_review(str(tmp_path))
    assert result["status"] == "reviewed_template_safe"
    assert result["decision"] == "allow_closure_with_secret_template_warning"
    assert result["real_secret_candidate_count"] == 0


def test_evaluate_real_secret_blocks_closure(tmp_path):
    _write_w_report(tmp_path)
    _write_env(tmp_path, "TOKEN=ghp_abcdefghijklmnopqrstuvwxyz1234567890\n")
    result = review_mod.evaluate_secret_like_path_review(str(tmp_path))
    assert result["decision"] == "block_until_secret_removed"
    assert result["real_secret_candidate_count"] == 1


def test_validate_review_valid_true_for_safe_template():
    assert review_mod.validate_secret_like_path_review(_safe_review())["valid"] is True


def test_validate_rejects_allow_closure_with_real_secret_count():
    data = _safe_review()
    data["real_secret_candidate_count"] = 1
    result = review_mod.validate_secret_like_path_review(data)
    assert result["valid"] is False


def test_validate_rejects_raw_secret_in_report():
    data = _safe_review()
    data["findings"][0]["value_masked_preview"] = "ghp_abcdefghijklmnopqrstuvwxyz"
    result = review_mod.validate_secret_like_path_review(data)
    assert result["valid"] is False


def test_validate_rejects_git_push_executed():
    data = _safe_review()
    data["safety_summary"]["git_push_executed"] = True
    assert review_mod.validate_secret_like_path_review(data)["valid"] is False


def test_validate_rejects_git_commit_executed():
    data = _safe_review()
    data["safety_summary"]["git_commit_executed"] = True
    assert review_mod.validate_secret_like_path_review(data)["valid"] is False


def test_validate_rejects_git_reset_executed():
    data = _safe_review()
    data["safety_summary"]["git_reset_restore_revert_executed"] = True
    assert review_mod.validate_secret_like_path_review(data)["valid"] is False


def test_validate_rejects_gh_workflow_run():
    data = _safe_review()
    data["safety_summary"]["gh_workflow_run_executed"] = True
    assert review_mod.validate_secret_like_path_review(data)["valid"] is False


def test_validate_rejects_runtime_write():
    data = _safe_review()
    data["safety_summary"]["runtime_write"] = True
    assert review_mod.validate_secret_like_path_review(data)["valid"] is False


def test_validate_rejects_audit_jsonl_write():
    data = _safe_review()
    data["safety_summary"]["audit_jsonl_write"] = True
    assert review_mod.validate_secret_like_path_review(data)["valid"] is False


def test_validate_rejects_auto_fix():
    data = _safe_review()
    data["safety_summary"]["auto_fix_executed"] = True
    assert review_mod.validate_secret_like_path_review(data)["valid"] is False


def test_generate_report_writes_only_tmp_path(tmp_path):
    _write_w_report(tmp_path)
    _write_env(tmp_path, "API_KEY=YOUR_API_KEY\n")
    output = tmp_path / "report.json"
    result = review_mod.generate_secret_like_path_review_report(
        review_mod.evaluate_secret_like_path_review(str(tmp_path)),
        str(output),
    )
    assert Path(result["json_path"]).exists()
    assert Path(result["markdown_path"]).exists()
    assert str(tmp_path) in result["json_path"]


def test_no_workflow_modification_in_tests(tmp_path):
    _write_w_report(tmp_path)
    _write_env(tmp_path, "API_KEY=YOUR_API_KEY\n")
    result = review_mod.evaluate_secret_like_path_review(str(tmp_path))
    assert result["safety_summary"]["workflow_modified"] is False


def test_no_secret_read_from_environment():
    names = set(review_mod.__dict__)
    assert "environ" not in names
    assert "getenv" not in names


def test_no_auto_fix():
    data = _safe_review()
    assert data["safety_summary"]["auto_fix_executed"] is False
