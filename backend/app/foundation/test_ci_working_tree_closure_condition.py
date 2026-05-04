"""R241-16W: Working Tree Closure Condition Resolution — tests."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Generator

import pytest

from app.foundation.ci_working_tree_closure_condition import (
    WorkingTreeClosureDecision,
    WorkingTreeClosureRiskLevel,
    WorkingTreeClosureStatus,
    WorkingTreeDirtyScope,
    _now,
    _root,
    _run_git,
    build_working_tree_closure_checks,
    classify_working_tree_dirty_files,
    evaluate_working_tree_closure_condition,
    generate_working_tree_closure_condition_report,
    inspect_current_working_tree_condition,
    load_r241_16v_closure_review,
    validate_working_tree_closure_condition,
    verify_delivery_artifacts_unchanged_since_r241_16u,
    verify_workflow_files_unchanged_for_closure,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def patch_report_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path, None, None]:
    """Set up isolated test environment.

    Structure:
      root_dir (tmp_path/"project") = test git repo
      migration_reports/ is in .gitignore so it's invisible to git status
      Files at root_dir/migration_reports/foundation_audit/ = where the code looks

    Key insight: .gitignore must exist BEFORE git add -A so migration_reports/
    is never tracked. Then we create migration_reports/ AFTER the commit,
    so git status --porcelain=v1 stays clean.
    """
    root_dir = tmp_path / "project"
    root_dir.mkdir()

    # .gitignore MUST be created before git add -A
    (root_dir / ".gitignore").write_text("migration_reports/\n", encoding="utf-8")

    workflow_dir = root_dir / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "foundation-manual-dispatch.yml").write_text(
        "name: Foundation Manual\non: workflow_dispatch\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "init"], cwd=str(root_dir), capture_output=True, shell=False)
    for cmd in [
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Test User"],
        ["git", "add", "-A"],
        ["git", "commit", "-m", "init"],
    ]:
        subprocess.run(cmd, cwd=str(root_dir), capture_output=True, shell=False)

    # PATCH module-level constants BEFORE creating migration_reports
    monkeypatch.setattr(
        "app.foundation.ci_working_tree_closure_condition.ROOT",
        root_dir,
    )
    monkeypatch.setattr(
        "app.foundation.ci_working_tree_closure_condition.REPORT_DIR",
        root_dir / "migration_reports" / "foundation_audit",
    )

    # Create migration_reports/ AFTER the commit — it is now gitignored
    report_dir = root_dir / "migration_reports" / "foundation_audit"
    report_dir.mkdir(parents=True, exist_ok=True)

    # Pre-create baseline delivery artifacts
    patch_data = b"patch content"
    bundle_data = b"bundle content"
    manifest_data = {
        "patch_sha256": hashlib.sha256(patch_data).hexdigest(),
        "bundle_sha256": hashlib.sha256(bundle_data).hexdigest(),
    }
    r241_16v_report = {
        "review_id": "R241-16V",
        "generated_at": _now(),
        "status": "passed_with_warnings",
        "decision": "approve_closure_with_conditions",
        "validated": True,
        "mutation_guard": {"staged_files": [], "head_hash": "abc123"},
        "closure_checks": [
            {"check_id": "mutation_no_working_tree", "passed": False,
             "risk_level": "medium", "description": "Working tree must be clean"},
        ],
    }
    r241_16u_index = {
        "source_commit_hash": "94908556cc2ca66c219d361f424954945eee9e67",
        "patch_sha256": hashlib.sha256(patch_data).hexdigest(),
        "bundle_sha256": hashlib.sha256(bundle_data).hexdigest(),
        "artifacts": [
            {"role": "patch", "filename": "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch"},
            {"role": "bundle", "filename": "R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle"},
        ],
    }
    (report_dir / "R241-16V_FOUNDATION_CI_DELIVERY_CLOSURE_REVIEW.json").write_text(
        json.dumps(r241_16v_report, indent=2), encoding="utf-8"
    )
    (report_dir / "R241-16U_DELIVERY_PACKAGE_INDEX.json").write_text(
        json.dumps(r241_16u_index, indent=2), encoding="utf-8"
    )
    (report_dir / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch").write_bytes(patch_data)
    (report_dir / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle").write_bytes(bundle_data)
    (report_dir / "R241-16S_PATCH_BUNDLE_MANIFEST.json").write_text(
        json.dumps(manifest_data), encoding="utf-8"
    )
    for fname in [
        "R241-16T_PATCH_DELIVERY_NOTE.md",
        "R241-16T_PATCH_BUNDLE_VERIFICATION_RESULT.json",
        "R241-16U_DELIVERY_PACKAGE_INDEX.md",
        "R241-16U_DELIVERY_FINAL_CHECKLIST.md",
        "R241-16U_HANDOFF_SUMMARY.md",
        "R241-16U_DELIVERY_PACKAGE_FINALIZATION_RESULT.json",
        "R241-16U_DELIVERY_PACKAGE_FINALIZATION_RESULT.md",
    ]:
        (report_dir / fname).write_text("content", encoding="utf-8")

    yield root_dir


# ── Test: load_r241_16v_closure_review ────────────────────────────────────────

class TestLoadR24116V:
    def test_accepts_passed_with_warnings(self) -> None:
        """R241-16V with passed_with_warnings status is accepted."""
        result = load_r241_16v_closure_review()
        assert result["is_valid_prerequisite"] is True
        assert result["exists"] is True
        assert result["loaded"] is True

    def test_requires_only_mutation_no_working_tree_failed(self) -> None:
        """Only mutation_no_working_tree failure is permitted."""
        result = load_r241_16v_closure_review()
        assert result["is_valid_prerequisite"] is True
        assert len(result["errors"]) == 0

    def test_requires_staged_0(self) -> None:
        """Staged files count must be 0."""
        result = load_r241_16v_closure_review()
        assert result["is_valid_prerequisite"] is True

    def test_requires_validated_true(self) -> None:
        """R241-16V must have validated=True."""
        result = load_r241_16v_closure_review()
        assert result["is_valid_prerequisite"] is True

    def test_rejects_missing_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing R241-16V report is rejected."""
        empty_root = tmp_path / "empty"
        empty_root.mkdir()
        monkeypatch.setattr(
            "app.foundation.ci_working_tree_closure_condition.ROOT",
            empty_root,
        )
        result = load_r241_16v_closure_review()
        assert result["exists"] is False
        assert result["is_valid_prerequisite"] is False

    def test_rejects_wrong_status(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """R241-16V with wrong status is rejected."""
        from app.foundation import ci_working_tree_closure_condition as m
        bad_report = {
            "review_id": "R241-16V",
            "generated_at": _now(),
            "status": "failed",
            "decision": "approve_closure",
            "validated": True,
            "mutation_guard": {"staged_files": [], "head_hash": "abc123"},
            "closure_checks": [],
        }
        # Write to the autouse fixture's REPORT_DIR (not the test's tmp_path)
        (m.REPORT_DIR / "R241-16V_FOUNDATION_CI_DELIVERY_CLOSURE_REVIEW.json").write_text(
            json.dumps(bad_report, indent=2), encoding="utf-8"
        )
        result = load_r241_16v_closure_review()
        assert result["is_valid_prerequisite"] is False

    def test_rejects_additional_failures(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """R241-16V with non-mutation failures is rejected."""
        from app.foundation import ci_working_tree_closure_condition as m
        bad_report = {
            "review_id": "R241-16V",
            "generated_at": _now(),
            "status": "passed_with_warnings",
            "decision": "approve_closure_with_conditions",
            "validated": True,
            "mutation_guard": {"staged_files": [], "head_hash": "abc123"},
            "closure_checks": [
                {"check_id": "mutation_no_working_tree", "passed": False, "risk_level": "medium"},
                {"check_id": "another_check", "passed": False, "risk_level": "high"},
            ],
        }
        (m.REPORT_DIR / "R241-16V_FOUNDATION_CI_DELIVERY_CLOSURE_REVIEW.json").write_text(
            json.dumps(bad_report, indent=2), encoding="utf-8"
        )
        result = load_r241_16v_closure_review()
        assert result["is_valid_prerequisite"] is False
        assert len(result["errors"]) > 0


# ── Test: inspect_current_working_tree_condition ─────────────────────────────

class TestInspectWorkingTree:
    def test_returns_correct_structure(self) -> None:
        """Returns dict with all required fields."""
        result = inspect_current_working_tree_condition()
        assert "branch" in result
        assert "head_hash" in result
        assert "staged_files" in result
        assert "dirty_files" in result
        assert "dirty_file_count" in result

    def test_detects_staged_files(self) -> None:
        """Detects staged files via git diff --cached."""
        from app.foundation.ci_working_tree_closure_condition import ROOT
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(ROOT))
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(ROOT))
        (ROOT / "test.txt").write_text("content", encoding="utf-8")
        subprocess.run(["git", "add", "test.txt"], cwd=str(ROOT))
        result = inspect_current_working_tree_condition()
        assert len(result["staged_files"]) == 1

    def test_detects_dirty_files(self) -> None:
        """Detects dirty files via git status --porcelain=v1."""
        from app.foundation.ci_working_tree_closure_condition import ROOT
        (ROOT / "dirty.txt").write_text("dirty", encoding="utf-8")
        result = inspect_current_working_tree_condition()
        assert result["dirty_file_count"] >= 1

    def test_handles_git_errors_gracefully(self, tmp_path: Path) -> None:
        """Handles non-git directory gracefully."""
        result = inspect_current_working_tree_condition(str(tmp_path))
        assert "errors" in result


# ── Test: classify_working_tree_dirty_files ────────────────────────────────────

class TestClassifyDirtyFiles:
    def test_classifies_delivery_scope(self) -> None:
        """Classifies R241-16S/R241-16T/R241-16U/R241-16V as delivery scope."""
        dirty_files = [
            {"path": "migration_reports/foundation_audit/R241-16S_PATCH_BUNDLE_MANIFEST.json", "status_code": " M"},
        ]
        result = classify_working_tree_dirty_files(dirty_files=dirty_files)
        assert result[0]["is_delivery_scope"] is True
        assert result[0]["scope"] == WorkingTreeDirtyScope.DELIVERY_SCOPE.value

    def test_classifies_workflow_scope(self) -> None:
        """Classifies .github/workflows/ as workflow scope."""
        dirty_files = [
            {"path": ".github/workflows/foundation-manual-dispatch.yml", "status_code": " M"},
        ]
        result = classify_working_tree_dirty_files(dirty_files=dirty_files)
        assert result[0]["is_workflow_scope"] is True
        assert result[0]["scope"] == WorkingTreeDirtyScope.WORKFLOW_SCOPE.value

    def test_classifies_runtime_scope(self) -> None:
        """Classifies runtime/ and action_queue/ as unrelated repo scope."""
        dirty_files = [
            {"path": "runtime/session.json", "status_code": " M"},
            {"path": "action_queue/tasks.json", "status_code": " M"},
        ]
        result = classify_working_tree_dirty_files(dirty_files=dirty_files)
        for r in result:
            assert r["is_runtime_scope"] is True

    def test_classifies_foundation_code_scope(self) -> None:
        """Classifies backend/app/foundation/ as foundation code scope."""
        dirty_files = [
            {"path": "backend/app/foundation/some_file.py", "status_code": " M"},
        ]
        result = classify_working_tree_dirty_files(dirty_files=dirty_files)
        assert result[0]["scope"] == WorkingTreeDirtyScope.FOUNDATION_CODE_SCOPE.value

    def test_classifies_unrelated_scope(self) -> None:
        """Unmatched files are unrelated repo scope."""
        dirty_files = [
            {"path": "README.md", "status_code": " M"},
            {"path": "frontend/src/index.ts", "status_code": " M"},
        ]
        result = classify_working_tree_dirty_files(dirty_files=dirty_files)
        for r in result:
            assert r["scope"] == WorkingTreeDirtyScope.UNRELATED_REPO_SCOPE.value

    def test_classifies_secret_like_paths(self) -> None:
        """Paths with secret-like patterns are flagged."""
        dirty_files = [
            {"path": "backend/.env", "status_code": " M"},
            {"path": "webhook_token.txt", "status_code": " M"},
        ]
        result = classify_working_tree_dirty_files(dirty_files=dirty_files)
        assert all(r["is_secret_like_path"] for r in result)


# ── Test: verify_delivery_artifacts_unchanged_since_r241_16u ──────────────────

class TestVerifyDeliveryArtifacts:
    def test_all_unchanged(self) -> None:
        """When all artifacts present and SHA matches, returns all_unchanged=True."""
        result = verify_delivery_artifacts_unchanged_since_r241_16u()
        assert result["all_unchanged"] is True
        assert result["sha256_verified"] is True

    def test_sha_mismatch_detected(self) -> None:
        """SHA mismatch is detected and reported."""
        from app.foundation.ci_working_tree_closure_condition import REPORT_DIR as _report_dir
        # Access through module reference so we get the patched value
        from app.foundation import ci_working_tree_closure_condition as m
        (m.REPORT_DIR / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch").write_bytes(b"wrong content")
        result = verify_delivery_artifacts_unchanged_since_r241_16u()
        assert result["sha256_verified"] is False
        assert len(result["checksum_mismatch_files"]) > 0

    def test_missing_artifact_detected(self) -> None:
        """Missing artifact is detected."""
        from app.foundation import ci_working_tree_closure_condition as m
        # Remove one artifact
        (m.REPORT_DIR / "R241-16T_PATCH_DELIVERY_NOTE.md").unlink()
        result = verify_delivery_artifacts_unchanged_since_r241_16u()
        assert result["all_unchanged"] is False
        assert len(result["errors"]) > 0


# ── Test: verify_workflow_files_unchanged_for_closure ─────────────────────────

class TestVerifyWorkflowFiles:
    def test_clean_workflow(self) -> None:
        """Clean workflow returns workflow_clean=True."""
        result = verify_workflow_files_unchanged_for_closure()
        assert result["workflow_clean"] is True
        assert result["target_workflow_dirty"] is False

    def test_dirty_workflow_detected(self) -> None:
        """Dirty workflow is detected."""
        from app.foundation.ci_working_tree_closure_condition import ROOT
        (ROOT / ".github" / "workflows" / "foundation-manual-dispatch.yml").write_text(
            "modified content", encoding="utf-8"
        )
        result = verify_workflow_files_unchanged_for_closure()
        assert result["target_workflow_dirty"] is True
        assert result["workflow_clean"] is False


# ── Test: build_working_tree_closure_checks ────────────────────────────────────

class TestBuildClosureChecks:
    def test_generates_nine_checks(self) -> None:
        """Generates exactly 9 closure checks."""
        r241_16v = {"is_valid_prerequisite": True, "errors": []}
        wt = {"staged_files": [], "dirty_file_count": 0}
        classified = []
        artifact = {"all_unchanged": True, "errors": [], "warnings": []}
        workflow = {"workflow_clean": True, "blocked_reasons": [], "warnings": []}

        checks = build_working_tree_closure_checks(
            r241_16v, wt, classified, artifact, workflow
        )
        assert len(checks) == 9

    def test_correct_check_ids(self) -> None:
        """All 9 check IDs are present."""
        r241_16v = {"is_valid_prerequisite": True, "errors": []}
        wt = {"staged_files": [], "dirty_file_count": 0}
        classified = []
        artifact = {"all_unchanged": True, "errors": [], "warnings": []}
        workflow = {"workflow_clean": True, "blocked_reasons": [], "warnings": []}

        checks = build_working_tree_closure_checks(
            r241_16v, wt, classified, artifact, workflow
        )
        check_ids = {c["check_id"] for c in checks}
        expected = {
            "r241_16v_prerequisite",
            "staged_area_empty",
            "delivery_artifacts_unchanged",
            "workflow_files_clean",
            "runtime_scope_clean",
            "no_secret_like_paths",
            "dirty_files_classified",
            "non_delivery_dirty_is_external",
            "receiver_handoff_valid",
        }
        assert check_ids == expected

    def test_checks_have_required_fields(self) -> None:
        """Each check has all required fields."""
        r241_16v = {"is_valid_prerequisite": True, "errors": []}
        wt = {"staged_files": [], "dirty_file_count": 0}
        classified = []
        artifact = {"all_unchanged": True, "errors": [], "warnings": []}
        workflow = {"workflow_clean": True, "blocked_reasons": [], "warnings": []}

        checks = build_working_tree_closure_checks(
            r241_16v, wt, classified, artifact, workflow
        )
        for c in checks:
            assert "check_id" in c
            assert "passed" in c
            assert "risk_level" in c
            assert "description" in c


# ── Test: evaluate_working_tree_closure_condition ────────────────────────────

class TestEvaluateWorkingTreeClosure:
    def test_clean_worktree_approve_full_closure(self) -> None:
        """Clean worktree with all artifacts intact yields approve_full_closure."""
        review = evaluate_working_tree_closure_condition()
        assert review["status"] == WorkingTreeClosureStatus.RESOLVED_CLEAN_WORKTREE.value
        assert review["decision"] == WorkingTreeClosureDecision.APPROVE_FULL_CLOSURE.value

    def test_external_dirty_approve_external_condition(self) -> None:
        """Non-delivery dirty files yield approve_delivery_closure_with_external_worktree_condition."""
        from app.foundation.ci_working_tree_closure_condition import ROOT
        # Create a dirty file in a non-delivery scope
        dirty_dir = ROOT / "backend" / "app" / "foundation"
        dirty_dir.mkdir(parents=True, exist_ok=True)
        (dirty_dir / "dirty.py").write_text("# dirty", encoding="utf-8")

        review = evaluate_working_tree_closure_condition()
        assert review["status"] == WorkingTreeClosureStatus.RESOLVED_EXTERNAL_WORKTREE_CONDITION.value
        assert review["decision"] == WorkingTreeClosureDecision.APPROVE_DELIVERY_CLOSURE_WITH_EXTERNAL_WORKTREE_CONDITION.value

    def test_delivery_scope_dirty_blocks_closure(self) -> None:
        """Delivery scope dirty files block closure."""
        from app.foundation.ci_working_tree_closure_condition import REPORT_DIR
        # Modify the patch file (SHA is verified against R241-16U index)
        (REPORT_DIR / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch").write_bytes(b"wrong content")

        review = evaluate_working_tree_closure_condition()
        assert review["status"] == WorkingTreeClosureStatus.BLOCKED_DELIVERY_SCOPE_DIRTY.value
        assert review["decision"] == WorkingTreeClosureDecision.BLOCK_CLOSURE_UNTIL_WORKTREE_REVIEW.value


# ── Test: validate_working_tree_closure_condition ──────────────────────────────

class TestValidateWorkingTreeClosure:
    def test_valid_review_passes(self) -> None:
        """Valid review passes validation."""
        review: dict[str, Any] = {
            "review_id": "R241-16W",
            "generated_at": _now(),
            "status": WorkingTreeClosureStatus.RESOLVED_EXTERNAL_WORKTREE_CONDITION.value,
            "decision": WorkingTreeClosureDecision.APPROVE_DELIVERY_CLOSURE_WITH_EXTERNAL_WORKTREE_CONDITION.value,
            "closure_checks": [],
            "dirty_files": [],
            "safety_summary": {
                "delivery_artifacts_verified": True,
                "workflow_files_verified": True,
                "staged_area_clean": True,
                "runtime_scope_clean": True,
                "no_secret_exposure": True,
            },
            "staged_files": [],
            "delivery_scope_dirty_files": [],
            "workflow_scope_dirty_files": [],
        }
        result = validate_working_tree_closure_condition(review)
        assert result["valid"] is True

    def test_missing_review_id_fails(self) -> None:
        """Missing review_id fails validation."""
        review: dict[str, Any] = {
            "generated_at": _now(),
            "status": WorkingTreeClosureStatus.RESOLVED_EXTERNAL_WORKTREE_CONDITION.value,
            "decision": WorkingTreeClosureDecision.APPROVE_DELIVERY_CLOSURE_WITH_EXTERNAL_WORKTREE_CONDITION.value,
            "closure_checks": [],
            "dirty_files": [],
            "safety_summary": {
                "delivery_artifacts_verified": True,
                "workflow_files_verified": True,
                "staged_area_clean": True,
                "runtime_scope_clean": True,
                "no_secret_exposure": True,
            },
        }
        result = validate_working_tree_closure_condition(review)
        assert result["valid"] is False

    def test_invalid_status_fails(self) -> None:
        """Invalid status enum fails validation."""
        review: dict[str, Any] = {
            "review_id": "R241-16W",
            "generated_at": _now(),
            "status": "invalid_status",
            "decision": WorkingTreeClosureDecision.APPROVE_DELIVERY_CLOSURE_WITH_EXTERNAL_WORKTREE_CONDITION.value,
            "closure_checks": [],
            "dirty_files": [],
            "safety_summary": {
                "delivery_artifacts_verified": True,
                "workflow_files_verified": True,
                "staged_area_clean": True,
                "runtime_scope_clean": True,
                "no_secret_exposure": True,
            },
        }
        result = validate_working_tree_closure_condition(review)
        assert result["valid"] is False

    def test_conditional_delivery_scope_blocks_approval(self) -> None:
        """Cannot approve with external condition when delivery scope is dirty."""
        review: dict[str, Any] = {
            "review_id": "R241-16W",
            "generated_at": _now(),
            "status": WorkingTreeClosureStatus.RESOLVED_EXTERNAL_WORKTREE_CONDITION.value,
            "decision": WorkingTreeClosureDecision.APPROVE_DELIVERY_CLOSURE_WITH_EXTERNAL_WORKTREE_CONDITION.value,
            "closure_checks": [],
            "dirty_files": [],
            "safety_summary": {
                "delivery_artifacts_verified": True,
                "workflow_files_verified": True,
                "staged_area_clean": True,
                "runtime_scope_clean": True,
                "no_secret_exposure": True,
            },
            "staged_files": [],
            "delivery_scope_dirty_files": ["some_artifact.json"],
            "workflow_scope_dirty_files": [],
        }
        result = validate_working_tree_closure_condition(review)
        assert result["valid"] is False


# ── Test: generate_working_tree_closure_condition_report ─────────────────────

class TestGenerateReport:
    def test_generates_both_json_and_md(self) -> None:
        """Generates both JSON and MD report files."""
        review: dict[str, Any] = {
            "review_id": "R241-16W",
            "generated_at": _now(),
            "status": WorkingTreeClosureStatus.RESOLVED_EXTERNAL_WORKTREE_CONDITION.value,
            "decision": WorkingTreeClosureDecision.APPROVE_DELIVERY_CLOSURE_WITH_EXTERNAL_WORKTREE_CONDITION.value,
            "closure_checks": [],
            "dirty_files": [],
            "safety_summary": {
                "delivery_artifacts_verified": True,
                "workflow_files_verified": True,
                "staged_area_clean": True,
                "runtime_scope_clean": True,
                "no_secret_exposure": True,
            },
            "staged_files": [],
            "delivery_scope_dirty_files": [],
            "workflow_scope_dirty_files": [],
            "r241_16v_status": "passed_with_warnings",
            "r241_16v_decision": "approve_closure_with_conditions",
            "r241_16v_failed_checks": [],
            "head_hash": "abc123",
            "branch": "main",
            "dirty_file_count": 0,
            "report_scope_dirty_files": [],
            "foundation_code_dirty_files": [],
            "unrelated_dirty_files": [],
            "closure_condition_classification": "external_worktree_condition",
            "receiver_next_steps": ["Review dirty files"],
            "warnings": [],
            "errors": [],
        }
        paths = generate_working_tree_closure_condition_report(review)
        assert Path(paths["json_path"]).exists()
        assert Path(paths["md_path"]).exists()

    def test_json_report_valid(self) -> None:
        """JSON report is valid JSON and passes validation."""
        review: dict[str, Any] = {
            "review_id": "R241-16W",
            "generated_at": _now(),
            "status": WorkingTreeClosureStatus.RESOLVED_EXTERNAL_WORKTREE_CONDITION.value,
            "decision": WorkingTreeClosureDecision.APPROVE_DELIVERY_CLOSURE_WITH_EXTERNAL_WORKTREE_CONDITION.value,
            "closure_checks": [],
            "dirty_files": [],
            "safety_summary": {
                "delivery_artifacts_verified": True,
                "workflow_files_verified": True,
                "staged_area_clean": True,
                "runtime_scope_clean": True,
                "no_secret_exposure": True,
            },
            "staged_files": [],
            "delivery_scope_dirty_files": [],
            "workflow_scope_dirty_files": [],
            "r241_16v_status": "passed_with_warnings",
            "r241_16v_decision": "approve_closure_with_conditions",
            "r241_16v_failed_checks": [],
            "head_hash": "abc123",
            "branch": "main",
            "dirty_file_count": 0,
            "report_scope_dirty_files": [],
            "foundation_code_dirty_files": [],
            "unrelated_dirty_files": [],
            "closure_condition_classification": "external_worktree_condition",
            "receiver_next_steps": ["Review dirty files"],
            "warnings": [],
            "errors": [],
        }
        paths = generate_working_tree_closure_condition_report(review)
        loaded = json.loads(Path(paths["json_path"]).read_text(encoding="utf-8"))
        assert loaded["validation_result"]["valid"] is True

    def test_md_report_has_required_sections(self) -> None:
        """MD report contains all required sections."""
        review: dict[str, Any] = {
            "review_id": "R241-16W",
            "generated_at": _now(),
            "status": WorkingTreeClosureStatus.RESOLVED_EXTERNAL_WORKTREE_CONDITION.value,
            "decision": WorkingTreeClosureDecision.APPROVE_DELIVERY_CLOSURE_WITH_EXTERNAL_WORKTREE_CONDITION.value,
            "closure_checks": [],
            "dirty_files": [],
            "safety_summary": {
                "delivery_artifacts_verified": True,
                "workflow_files_verified": True,
                "staged_area_clean": True,
                "runtime_scope_clean": True,
                "no_secret_exposure": True,
            },
            "staged_files": [],
            "delivery_scope_dirty_files": [],
            "workflow_scope_dirty_files": [],
            "r241_16v_status": "passed_with_warnings",
            "r241_16v_decision": "approve_closure_with_conditions",
            "r241_16v_failed_checks": [],
            "head_hash": "abc123",
            "branch": "main",
            "dirty_file_count": 0,
            "report_scope_dirty_files": [],
            "foundation_code_dirty_files": [],
            "unrelated_dirty_files": [],
            "closure_condition_classification": "external_worktree_condition",
            "receiver_next_steps": ["Step 1"],
            "warnings": [],
            "errors": [],
        }
        paths = generate_working_tree_closure_condition_report(review)
        md_content = Path(paths["md_path"]).read_text(encoding="utf-8")
        required_sections = [
            "## Current Working Tree State",
            "## Dirty File Classification",
            "## Safety Summary",
            "## Closure Checks",
            "## Receiver Next Steps",
            "## Forbidden Operations Check",
        ]
        for section in required_sections:
            assert section in md_content, f"Missing section: {section}"


# ── Test: Forbidden Operations ────────────────────────────────────────────────

class TestForbiddenOperations:
    def test_no_auto_fix_in_validation(self) -> None:
        """validate_working_tree_closure_condition performs no auto-fix."""
        review: dict[str, Any] = {
            "review_id": "R241-16W",
            "generated_at": _now(),
            "status": WorkingTreeClosureStatus.RESOLVED_EXTERNAL_WORKTREE_CONDITION.value,
            "decision": WorkingTreeClosureDecision.APPROVE_DELIVERY_CLOSURE_WITH_EXTERNAL_WORKTREE_CONDITION.value,
            "closure_checks": [],
            "dirty_files": [],
            "safety_summary": {
                "delivery_artifacts_verified": True,
                "workflow_files_verified": True,
                "staged_area_clean": True,
                "runtime_scope_clean": True,
                "no_secret_exposure": True,
            },
            "staged_files": [],
            "delivery_scope_dirty_files": [],
            "workflow_scope_dirty_files": [],
        }
        result = validate_working_tree_closure_condition(review)
        assert result["valid"] is True
        assert review.get("review_id") == "R241-16W"

    def test_generate_report_is_read_only(self) -> None:
        """generate_working_tree_closure_condition_report only writes report files."""
        review: dict[str, Any] = {
            "review_id": "R241-16W",
            "generated_at": _now(),
            "status": WorkingTreeClosureStatus.RESOLVED_EXTERNAL_WORKTREE_CONDITION.value,
            "decision": WorkingTreeClosureDecision.APPROVE_DELIVERY_CLOSURE_WITH_EXTERNAL_WORKTREE_CONDITION.value,
            "closure_checks": [],
            "dirty_files": [],
            "safety_summary": {
                "delivery_artifacts_verified": True,
                "workflow_files_verified": True,
                "staged_area_clean": True,
                "runtime_scope_clean": True,
                "no_secret_exposure": True,
            },
            "staged_files": [],
            "delivery_scope_dirty_files": [],
            "workflow_scope_dirty_files": [],
            "r241_16v_status": "passed_with_warnings",
            "r241_16v_decision": "approve_closure_with_conditions",
            "r241_16v_failed_checks": [],
            "head_hash": "abc123",
            "branch": "main",
            "dirty_file_count": 0,
            "report_scope_dirty_files": [],
            "foundation_code_dirty_files": [],
            "unrelated_dirty_files": [],
            "closure_condition_classification": "external_worktree_condition",
            "receiver_next_steps": [],
            "warnings": [],
            "errors": [],
        }
        paths = generate_working_tree_closure_condition_report(review)
        assert Path(paths["json_path"]).exists()
        assert Path(paths["md_path"]).exists()
