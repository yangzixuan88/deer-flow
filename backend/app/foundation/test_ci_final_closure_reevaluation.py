import json
from pathlib import Path

from backend.app.foundation import ci_final_closure_reevaluation as final


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _base_reports(root: Path, *, x_status: str = "reviewed_no_secret_like_content", real_count: int = 0) -> None:
    base = root / "migration_reports" / "foundation_audit"
    _write_json(base / "R241-16X_SECRET_LIKE_PATH_REVIEW.json", {
        "review": {
            "status": x_status,
            "decision": "allow_closure_no_secret" if x_status == "reviewed_no_secret_like_content" else "allow_closure_with_secret_template_warning",
            "target_path": "frontend/.env.example",
            "real_secret_candidate_count": real_count,
            "suspicious_value_count": 0,
            "safety_summary": {
                "raw_secret_value_emitted": False,
                "secret_environment_read": False,
                "runtime_write": False,
                "audit_jsonl_write": False,
                "action_queue_write": False,
                "workflow_modified": False,
            },
            "validation_result": {"valid": True, "errors": [], "warnings": []},
        },
        "validation": {"valid": True, "errors": [], "warnings": []},
    })
    _write_json(base / "R241-16W_WORKING_TREE_CLOSURE_CONDITION.json", {
        "status": "blocked_unknown_dirty_state",
        "decision": "block_closure_until_worktree_review",
        "head_hash": final.SOURCE_COMMIT_HASH,
        "staged_files": [],
        "delivery_scope_dirty_files": [],
        "workflow_scope_dirty_files": [],
        "closure_checks": [
            {"check_id": "no_secret_like_paths", "passed": False, "blocked_reasons": ["Secret-like path: frontend/.env.example"]}
        ],
        "dirty_files": [{"path": "frontend/.env.example", "is_secret_like_path": True}],
        "safety_summary": {
            "runtime_scope_clean": True,
            "delivery_artifacts_verified": True,
            "workflow_files_verified": True,
        },
    })
    _write_json(base / "R241-16V_FOUNDATION_CI_DELIVERY_CLOSURE_REVIEW.json", {
        "status": "passed_with_warnings",
        "decision": "approve_closure_with_conditions",
    })
    _write_json(base / "R241-16S_PATCH_BUNDLE_GENERATION_RESULT.json", {
        "status": "generated",
        "decision": "generate_patch_and_bundle",
        "source_commit_hash": final.SOURCE_COMMIT_HASH,
        "source_commit_only_target_workflow": True,
        "patch_generated": True,
        "bundle_generated": True,
        "manifest_generated": True,
        "validation": {"valid": True},
        "artifacts": [
            {"artifact_type": "patch", "safe_to_share": True},
            {"artifact_type": "bundle", "safe_to_share": True},
            {"artifact_type": "manifest", "safe_to_share": True},
        ],
    })
    _write_json(base / "R241-16T_PATCH_BUNDLE_VERIFICATION_RESULT.json", {})
    _write_json(base / "R241-16U_DELIVERY_PACKAGE_FINALIZATION_RESULT.json", {
        "status": "finalized_with_warnings",
        "decision": "approve_handoff_with_warnings",
        "source_commit_hash": final.SOURCE_COMMIT_HASH,
        "source_changed_files": [final.TARGET_WORKFLOW],
        "verified_bundle_state": {
            "valid": True,
            "patch_safe": True,
            "bundle_safe": True,
            "source_commit_hash": final.SOURCE_COMMIT_HASH,
            "source_changed_files": [final.TARGET_WORKFLOW],
        },
        "validation": {"valid": True},
    })
    for name in [
        "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch",
        "R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle",
        "R241-16S_PATCH_BUNDLE_MANIFEST.json",
        "R241-16U_DELIVERY_PACKAGE_INDEX.json",
        "R241-16U_DELIVERY_FINAL_CHECKLIST.md",
        "R241-16U_HANDOFF_SUMMARY.md",
    ]:
        (base / name).write_text("artifact", encoding="utf-8")


def _state(*, dirty=None, staged=None, workflow=None, runtime=None, delivery=None):
    dirty = dirty if dirty is not None else [{"path": "frontend/.env.example", "status_code": " M"}]
    return {
        "branch": "main...origin/main [ahead 1]",
        "head_hash": final.SOURCE_COMMIT_HASH,
        "staged_files": staged or [],
        "staged_file_count": len(staged or []),
        "dirty_files": dirty,
        "dirty_file_count": len(dirty),
        "classified_dirty_files": dirty,
        "workflow_dirty_files": workflow or [],
        "workflow_dirty_count": len(workflow or []),
        "runtime_dirty_files": runtime or [],
        "runtime_dirty_count": len(runtime or []),
        "report_dirty_files": [],
        "report_dirty_count": 0,
        "delivery_dirty_files": delivery or [],
        "delivery_dirty_count": len(delivery or []),
        "remote_target_workflow_present": False,
        "warnings": [],
        "errors": [],
    }


def test_load_r241_16x_accepts_no_secret_like_content(tmp_path):
    _base_reports(tmp_path)
    assert final.load_r241_16x_secret_like_review(str(tmp_path))["passed"] is True


def test_load_r241_16x_accepts_template_safe(tmp_path):
    _base_reports(tmp_path, x_status="reviewed_template_safe")
    assert final.load_r241_16x_secret_like_review(str(tmp_path))["passed"] is True


def test_load_r241_16x_blocks_real_secret_candidate(tmp_path):
    _base_reports(tmp_path, real_count=1)
    assert final.load_r241_16x_secret_like_review(str(tmp_path))["passed"] is False


def test_load_r241_16w_requires_no_secret_like_paths_failure(tmp_path):
    _base_reports(tmp_path)
    assert final.load_r241_16w_condition_for_reevaluation(str(tmp_path))["passed"] is True


def test_inspect_current_closure_state_uses_diff_cached_for_staged_files(monkeypatch, tmp_path):
    _base_reports(tmp_path)
    calls = []

    def fake_run(argv, root=None, timeout=30):
        calls.append(argv)
        out = "staged.txt\n" if argv[:4] == ["git", "diff", "--cached", "--name-only"] else ""
        return {"argv": argv, "command_executed": True, "exit_code": 0, "stdout": out, "stderr": ""}

    monkeypatch.setattr(final, "_run_git", fake_run)
    result = final.inspect_current_closure_state(str(tmp_path))
    assert result["staged_files"] == ["staged.txt"]
    assert ["git", "diff", "--cached", "--name-only"] in calls


def test_dirty_state_reclassifies_frontend_env_example_as_external_condition(monkeypatch, tmp_path):
    _base_reports(tmp_path)
    monkeypatch.setattr(final, "inspect_current_closure_state", lambda root=None: _state())
    result = final.reevaluate_dirty_state_with_secret_review(str(tmp_path))
    assert result["secret_like_blocker_resolved"] is True
    assert result["accepted_as_external_condition"] is True


def test_dirty_state_blocks_workflow_dirty_files(monkeypatch, tmp_path):
    _base_reports(tmp_path)
    monkeypatch.setattr(final, "inspect_current_closure_state", lambda root=None: _state(workflow=[".github/workflows/x.yml"]))
    result = final.reevaluate_dirty_state_with_secret_review(str(tmp_path))
    assert result["accepted_as_external_condition"] is False


def test_dirty_state_blocks_runtime_dirty_files(monkeypatch, tmp_path):
    _base_reports(tmp_path)
    monkeypatch.setattr(final, "inspect_current_closure_state", lambda root=None: _state(runtime=["runtime/state.json"]))
    result = final.reevaluate_dirty_state_with_secret_review(str(tmp_path))
    assert result["accepted_as_external_condition"] is False


def test_dirty_state_blocks_staged_files(monkeypatch, tmp_path):
    _base_reports(tmp_path)
    monkeypatch.setattr(final, "inspect_current_closure_state", lambda root=None: _state(staged=["x.txt"]))
    result = final.reevaluate_dirty_state_with_secret_review(str(tmp_path))
    assert result["accepted_as_external_condition"] is False


def test_delivery_artifacts_still_valid(tmp_path):
    _base_reports(tmp_path)
    assert final.verify_delivery_artifacts_still_valid(str(tmp_path))["valid"] is True


def test_delivery_artifacts_missing_blocks(tmp_path):
    _base_reports(tmp_path)
    (tmp_path / "migration_reports" / "foundation_audit" / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch").unlink()
    assert final.verify_delivery_artifacts_still_valid(str(tmp_path))["valid"] is False


def test_final_safety_rejects_git_push_executed():
    safety = final.verify_final_closure_safety()
    safety["git_push_executed"] = True
    review = _review(safety=safety)
    assert final.validate_final_closure_reevaluation(review)["valid"] is False


def test_final_safety_rejects_git_commit_executed():
    safety = final.verify_final_closure_safety()
    safety["git_commit_executed"] = True
    assert final.validate_final_closure_reevaluation(_review(safety=safety))["valid"] is False


def test_final_safety_rejects_git_reset_executed():
    safety = final.verify_final_closure_safety()
    safety["git_reset_restore_revert_executed"] = True
    assert final.validate_final_closure_reevaluation(_review(safety=safety))["valid"] is False


def test_final_safety_rejects_gh_workflow_run():
    safety = final.verify_final_closure_safety()
    safety["gh_workflow_run_executed"] = True
    assert final.validate_final_closure_reevaluation(_review(safety=safety))["valid"] is False


def test_final_checks_include_secret_like_blocker_resolved(tmp_path):
    _base_reports(tmp_path)
    checks = final.build_final_closure_checks(str(tmp_path))["checks"]
    assert any(c["check_id"] == "secret_like_blocker_resolved" for c in checks)


def _delivery_valid():
    return {
        "valid": True,
        "source_commit_hash": final.SOURCE_COMMIT_HASH,
        "source_changed_files": [final.TARGET_WORKFLOW],
        "required_artifacts_present": True,
        "warnings": [],
        "errors": [],
    }


def _review(*, safety=None, workflow=None, runtime=None, staged=None, real_count=0, status="closed_with_external_worktree_condition"):
    return {
        "status": status,
        "decision": "approve_final_closure_with_external_worktree_condition",
        "r241_16x_summary": {"review": {"real_secret_candidate_count": real_count}},
        "workflow_state": {"workflow_dirty_files": workflow or [], "workflow_dirty_count": len(workflow or [])},
        "runtime_state": {"runtime_dirty_files": runtime or [], "runtime_dirty_count": len(runtime or [])},
        "staged_files": staged or [],
        "dirty_file_count": 1 if status == "closed_with_external_worktree_condition" else 0,
        "delivery_artifacts_state": _delivery_valid(),
        "closure_checks": [{"check_id": "ok", "passed": True, "required_for_final_closure": True}],
        "safety_summary": safety or final.verify_final_closure_safety(),
    }


def test_evaluate_closed_with_external_worktree_condition(monkeypatch, tmp_path):
    _base_reports(tmp_path)
    monkeypatch.setattr(final, "inspect_current_closure_state", lambda root=None: _state())
    result = final.evaluate_final_closure_reevaluation(str(tmp_path))
    assert result["status"] == "closed_with_external_worktree_condition"


def test_evaluate_closed_clean_when_no_dirty_files(monkeypatch, tmp_path):
    _base_reports(tmp_path)
    monkeypatch.setattr(final, "inspect_current_closure_state", lambda root=None: _state(dirty=[]))
    result = final.evaluate_final_closure_reevaluation(str(tmp_path))
    assert result["status"] == "closed_clean"


def test_evaluate_blocked_secret_like_path_unresolved(monkeypatch, tmp_path):
    _base_reports(tmp_path, real_count=1)
    monkeypatch.setattr(final, "inspect_current_closure_state", lambda root=None: _state())
    result = final.evaluate_final_closure_reevaluation(str(tmp_path))
    assert result["status"] == "blocked_secret_like_path_unresolved"


def test_evaluate_blocked_workflow_dirty(monkeypatch, tmp_path):
    _base_reports(tmp_path)
    monkeypatch.setattr(final, "inspect_current_closure_state", lambda root=None: _state(workflow=[".github/workflows/x.yml"]))
    result = final.evaluate_final_closure_reevaluation(str(tmp_path))
    assert result["status"] == "blocked_workflow_dirty"


def test_validate_final_closure_valid_true_for_external_condition():
    assert final.validate_final_closure_reevaluation(_review())["valid"] is True


def test_validate_rejects_closure_if_real_secret_candidate_count_gt_0():
    assert final.validate_final_closure_reevaluation(_review(real_count=1))["valid"] is False


def test_validate_rejects_closure_if_workflow_dirty():
    assert final.validate_final_closure_reevaluation(_review(workflow=[".github/workflows/x.yml"]))["valid"] is False


def test_validate_rejects_closure_if_runtime_dirty():
    assert final.validate_final_closure_reevaluation(_review(runtime=["runtime/x"]))["valid"] is False


def test_validate_rejects_closure_if_staged_files_present():
    assert final.validate_final_closure_reevaluation(_review(staged=["x.txt"]))["valid"] is False


def test_validate_rejects_runtime_write():
    safety = final.verify_final_closure_safety()
    safety["runtime_write"] = True
    assert final.validate_final_closure_reevaluation(_review(safety=safety))["valid"] is False


def test_validate_rejects_audit_jsonl_write():
    safety = final.verify_final_closure_safety()
    safety["audit_jsonl_write"] = True
    assert final.validate_final_closure_reevaluation(_review(safety=safety))["valid"] is False


def test_validate_rejects_auto_fix():
    safety = final.verify_final_closure_safety()
    safety["auto_fix_executed"] = True
    assert final.validate_final_closure_reevaluation(_review(safety=safety))["valid"] is False


def test_generate_report_writes_only_tmp_path(tmp_path, monkeypatch):
    _base_reports(tmp_path)
    monkeypatch.setattr(final, "inspect_current_closure_state", lambda root=None: _state())
    result = final.generate_final_closure_reevaluation_report(
        final.evaluate_final_closure_reevaluation(str(tmp_path)),
        str(tmp_path / "final.json"),
    )
    assert Path(result["json_path"]).exists()
    assert Path(result["markdown_path"]).exists()
    assert str(tmp_path) in result["json_path"]


def test_no_workflow_modification_in_tests():
    assert final.verify_final_closure_safety()["workflow_modified"] is False


def test_no_secret_env_read():
    assert final.verify_final_closure_safety()["secret_env_read"] is False


def test_no_raw_secret_emitted():
    assert final.verify_final_closure_safety()["raw_secret_emitted"] is False


def test_no_auto_fix():
    assert final.verify_final_closure_safety()["auto_fix_executed"] is False

