"""R241-16V: Foundation CI Delivery Closure Review — tests."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Generator

import pytest

from app.foundation.ci_delivery_closure_review import (
    ROOT,
    REPORT_DIR,
    STAGE_CHAIN,
    DELIVERY_ARTIFACTS,
    SOURCE_COMMIT_HASH,
    TARGET_WORKFLOW,
    DeliveryClosureArtifactSummary,
    DeliveryClosureCheck,
    DeliveryClosureDecision,
    DeliveryClosureDomain,
    DeliveryClosureReview,
    DeliveryClosureRiskLevel,
    DeliveryClosureStatus,
    _now,
    _root,
    _run_git,
    _safe_baseline,
    _sha256,
    build_delivery_closure_checks,
    build_receiver_next_steps,
    collect_foundation_ci_delivery_stage_chain,
    evaluate_foundation_ci_delivery_closure,
    generate_delivery_closure_review_report,
    load_delivery_finalization_state,
    validate_delivery_closure_review,
    verify_delivery_artifacts_for_closure,
    verify_no_mutation_during_closure_review,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def patch_report_dir(root: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path, None, None]:
    """Patch module-level REPORT_DIR so tests use isolated tmp_path."""
    test_report_dir = root / "migration_reports" / "foundation_audit"
    test_report_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "app.foundation.ci_delivery_closure_review.REPORT_DIR",
        test_report_dir,
    )
    yield test_report_dir


@pytest.fixture
def root(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a self-contained root dir with required git and artifact structure."""
    root_dir = tmp_path / "project"
    root_dir.mkdir()
    migration_dir = root_dir / "migration_reports" / "foundation_audit"
    migration_dir.mkdir(parents=True)

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

    yield root_dir


@pytest.fixture
def delivery_artifacts(root: Path) -> dict[Path, Path]:
    """Create all delivery artifacts in the report dir."""
    migration_dir = root / "migration_reports" / "foundation_audit"

    patch_data = b"patch content here"
    bundle_data = b"bundle content here"
    manifest_data = {
        "source_commit_hash": SOURCE_COMMIT_HASH,
        "source_changed_files": [TARGET_WORKFLOW],
        "patch_sha256": hashlib.sha256(patch_data).hexdigest(),
        "bundle_sha256": hashlib.sha256(bundle_data).hexdigest(),
        "generation_timestamp": _now(),
    }
    verification_data = {
        "status": "verified_with_warnings",
        "decision": "approve_delivery_artifacts",
        "validation": {"valid": True, "blocked_reasons": []},
        "patch_inspection": {
            "safe_to_share": True,
            "patch_exists": True,
            "patch_sha": hashlib.sha256(patch_data).hexdigest(),
            "no_pr_push_schedule_triggers": True,
            "no_secrets_found": True,
            "no_auto_fix": True,
            "secrets_in_patch": [],
            "warnings": [],
        },
        "bundle_inspection": {
            "safe_to_share": True,
            "bundle_exists": True,
            "bundle_sha": hashlib.sha256(bundle_data).hexdigest(),
            "bundle_verify_passed": True,
            "warnings": [],
        },
        "source_commit_hash": SOURCE_COMMIT_HASH,
        "source_changed_files": [TARGET_WORKFLOW],
        "mutation_guard": {"all_passed": True, "checks": []},
        "delivery_note_result": {"note_exists": True},
        "warnings": [],
    }
    delivery_note_content = "# R241-16T Patch Delivery Note\n\nApply with: git am\n"
    index_data = {"delivery_artifacts": [], "handoff_timestamp": _now()}
    checklist_content = "# Final Checklist\n- [ ] Verify patch\n"
    summary_content = "# Handoff Summary\nAll artifacts verified.\n"
    finalization_data = {
        "status": "finalized",
        "decision": "approve_handoff",
        "validation": {"valid": True, "blocked_reasons": []},
        "mutation_guard": {"all_passed": True, "checks": []},
        "generated_at": _now(),
    }

    artifacts: dict[Path, bytes] = {
        migration_dir / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch": patch_data,
        migration_dir / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle": bundle_data,
        migration_dir / "R241-16S_PATCH_BUNDLE_MANIFEST.json": json.dumps(manifest_data, indent=2).encode(),
        migration_dir / "R241-16T_PATCH_BUNDLE_VERIFICATION_RESULT.json": json.dumps(verification_data, indent=2).encode(),
        migration_dir / "R241-16T_PATCH_DELIVERY_NOTE.md": delivery_note_content.encode(),
        migration_dir / "R241-16U_DELIVERY_PACKAGE_INDEX.json": json.dumps(index_data, indent=2).encode(),
        migration_dir / "R241-16U_DELIVERY_PACKAGE_INDEX.md": "# Delivery Package Index\n".encode(),
        migration_dir / "R241-16U_DELIVERY_FINAL_CHECKLIST.md": checklist_content.encode(),
        migration_dir / "R241-16U_HANDOFF_SUMMARY.md": summary_content.encode(),
        migration_dir / "R241-16U_DELIVERY_PACKAGE_FINALIZATION_RESULT.json": json.dumps(finalization_data, indent=2).encode(),
        migration_dir / "R241-16U_DELIVERY_PACKAGE_FINALIZATION_REPORT.md": "# Finalization Report\n".encode(),
    }

    for path, data in artifacts.items():
        path.write_bytes(data)

    return artifacts


@pytest.fixture
def stage_reports(root: Path) -> None:
    """Create stage reports for R241-16A, R241-16S, R241-16T, R241-16U."""
    migration_dir = root / "migration_reports" / "foundation_audit"
    for stage_id in ["R241-16A", "R241-16S", "R241-16T", "R241-16U"]:
        report_path = migration_dir / f"{stage_id}_FOUNDATION_CI_STAGE_REVIEW.json"
        report_path.write_text(json.dumps({
            "stage_id": stage_id,
            "status": "passed",
            "decision": "approve_closure",
            "generated_at": _now(),
        }), encoding="utf-8")


# ── Tests ───────────────────────────────────────────────────────────────────────

class TestEnums:
    def test_delivery_closure_status_values(self):
        assert DeliveryClosureStatus.PASSED.value == "passed"
        assert DeliveryClosureStatus.PASSED_WITH_WARNINGS.value == "passed_with_warnings"
        assert DeliveryClosureStatus.FAILED.value == "failed"
        assert DeliveryClosureStatus.SKIPPED.value == "skipped"
        assert DeliveryClosureStatus.UNKNOWN.value == "unknown"

    def test_delivery_closure_decision_values(self):
        assert DeliveryClosureDecision.APPROVE_CLOSURE.value == "approve_closure"
        assert DeliveryClosureDecision.APPROVE_CLOSURE_WITH_CONDITIONS.value == "approve_closure_with_conditions"
        assert DeliveryClosureDecision.BLOCK_CLOSURE.value == "block_closure"
        assert DeliveryClosureDecision.DEFER.value == "defer"
        assert DeliveryClosureDecision.UNKNOWN.value == "unknown"

    def test_delivery_closure_risk_level_values(self):
        assert DeliveryClosureRiskLevel.LOW.value == "low"
        assert DeliveryClosureRiskLevel.MEDIUM.value == "medium"
        assert DeliveryClosureRiskLevel.HIGH.value == "high"
        assert DeliveryClosureRiskLevel.CRITICAL.value == "critical"
        assert DeliveryClosureRiskLevel.UNKNOWN.value == "unknown"

    def test_delivery_closure_domain_values(self):
        domains = [d.value for d in DeliveryClosureDomain]
        assert "safety" in domains
        assert "ci_matrix" in domains
        assert "manual_workflow" in domains
        assert "patch_bundle" in domains
        assert "delivery_package" in domains
        assert "tests" in domains
        assert "handoff" in domains
        assert "artifact_integrity" in domains
        assert "mutation_guard" in domains
        assert "chain_completeness" in domains


class TestDeliveryClosureCheck:
    def test_check_to_dict(self):
        check = DeliveryClosureCheck(
            domain=DeliveryClosureDomain.ARTIFACT_INTEGRITY.value,
            check_id="test_check",
            description="Test check",
            passed=True,
            status="passed",
            risk_level=DeliveryClosureRiskLevel.LOW.value,
            details={"key": "value"},
            recommendations=["Rec 1"],
        )
        d = check.to_dict()
        assert d["check_id"] == "test_check"
        assert d["passed"] is True
        assert d["domain"] == "artifact_integrity"
        assert d["recommendations"] == ["Rec 1"]

    def test_check_defaults(self):
        check = DeliveryClosureCheck(
            domain=DeliveryClosureDomain.MUTATION_GUARD.value,
            check_id="minimal",
            description="Minimal check",
            passed=False,
            status="failed",
            risk_level=DeliveryClosureRiskLevel.HIGH.value,
        )
        assert check.details == {}
        assert check.recommendations == []


class TestDeliveryClosureArtifactSummary:
    def test_artifact_summary_to_dict(self):
        art = DeliveryClosureArtifactSummary(
            filename="test.txt",
            role="patch",
            exists=True,
            sha256="a" * 64,
            size_bytes=1024,
            required=True,
            validation_errors=[],
        )
        d = art.to_dict()
        assert d["filename"] == "test.txt"
        assert d["exists"] is True
        assert d["sha256"] == "a" * 64
        assert d["required"] is True

    def test_artifact_summary_missing(self):
        art = DeliveryClosureArtifactSummary(
            filename="missing.txt",
            role="bundle",
            exists=False,
            required=True,
            validation_errors=["Required artifact missing"],
        )
        d = art.to_dict()
        assert d["exists"] is False
        assert "Required artifact missing" in d["validation_errors"]


class TestDeliveryClosureReview:
    def test_review_to_dict(self):
        review = DeliveryClosureReview(
            review_id="R241-16V",
            stage_chain=[],
            artifact_summary=[],
            closure_checks=[],
            receiver_next_steps=["Step 1"],
            mutation_guard={},
            decision=DeliveryClosureDecision.APPROVE_CLOSURE.value,
            status=DeliveryClosureStatus.PASSED.value,
            risk_level=DeliveryClosureRiskLevel.LOW.value,
            generated_at="2026-04-26T00:00:00Z",
        )
        d = review.to_dict()
        assert d["review_id"] == "R241-16V"
        assert d["decision"] == "approve_closure"
        assert d["status"] == "passed"

    def test_review_validation_errors(self):
        review = DeliveryClosureReview(
            review_id="",
            stage_chain=[],
            artifact_summary=[],
            closure_checks=[],
            receiver_next_steps=[],
            mutation_guard={},
            decision="invalid_decision",
            status="invalid_status",
            risk_level="invalid_risk",
            generated_at="",
        )
        validation = validate_delivery_closure_review(review)
        assert validation["valid"] is False
        assert len(validation["errors"]) > 0


class TestHelpers:
    def test_now_returns_iso_format(self):
        now = _now()
        assert "T" in now
        assert "Z" in now or "+" in now or now.endswith("000000")

    def test_root_default(self):
        r = _root(None)
        assert r == ROOT

    def test_root_with_explicit_path(self, tmp_path: Path):
        explicit = tmp_path / "explicit_root"
        explicit.mkdir()
        result = _root(str(explicit))
        assert result == explicit

    def test_root_with_nonexistent_path(self, tmp_path: Path):
        nonexistent = tmp_path / "does_not_exist"
        result = _root(str(nonexistent))
        assert result == ROOT

    def test_sha256_computes(self, tmp_path: Path):
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"hello world")
        sha = _sha256(test_file)
        expected = hashlib.sha256(b"hello world").hexdigest()
        assert sha == expected

    def test_run_git_success(self, root: Path):
        result = _run_git(["git", "rev-parse", "HEAD"], str(root))
        assert result["command_executed"] is True
        assert result["exit_code"] == 0
        assert result["stdout"].strip()

    def test_run_git_invalid_command(self, root: Path):
        result = _run_git(["git", "nonexistent-subcommand"], str(root))
        assert result["command_executed"] is True
        assert result["exit_code"] != 0

    def test_safe_baseline(self, root: Path):
        baseline = _safe_baseline(str(root))
        assert "head_hash" in baseline
        assert "branch" in baseline
        assert "staged_files" in baseline
        assert "git_status_short" in baseline
        assert baseline["head_hash"] is not None


class TestLoadDeliveryFinalizationState:
    def test_load_when_not_exists(self, root: Path, patch_report_dir: Path):
        state = load_delivery_finalization_state(str(root))
        assert state["loaded"] is True
        assert state["exists"] is False
        assert len(state["errors"]) > 0

    def test_load_when_exists_valid_json(
        self, root: Path, patch_report_dir: Path, delivery_artifacts: dict
    ):
        state = load_delivery_finalization_state(str(root))
        assert state["loaded"] is True
        assert state["exists"] is True
        assert state["data"] is not None
        assert state["data"]["status"] == "finalized"

    def test_load_when_exists_invalid_json(self, root: Path, patch_report_dir: Path):
        path = patch_report_dir / "R241-16U_DELIVERY_PACKAGE_FINALIZATION_RESULT.json"
        path.write_text("not valid json{", encoding="utf-8")
        state = load_delivery_finalization_state(str(root))
        assert state["exists"] is True
        assert state["loaded"] is True
        assert len(state["errors"]) > 0


class TestCollectStageChain:
    def test_collect_all_stages_present(self, root: Path, stage_reports: None):
        chain = collect_foundation_ci_delivery_stage_chain(str(root))
        assert len(chain) == len(STAGE_CHAIN)
        assert chain[0]["stage_id"] == "R241-16A"
        assert chain[-1]["stage_id"] == "R241-16U"

    def test_collect_stages_none_exist(self, root: Path):
        chain = collect_foundation_ci_delivery_stage_chain(str(root))
        assert len(chain) == len(STAGE_CHAIN)
        for stage in chain:
            assert stage["report_json_exists"] is False
            assert stage["report_md_exists"] is False

    def test_collect_critical_stages(self, root: Path, stage_reports: None):
        chain = collect_foundation_ci_delivery_stage_chain(str(root))
        critical_ids = {"R241-16A", "R241-16S", "R241-16T", "R241-16U"}
        found = {s["stage_id"] for s in chain if s["report_json_exists"]}
        assert found.issuperset({"R241-16A", "R241-16S", "R241-16T", "R241-16U"})


class TestVerifyDeliveryArtifactsForClosure:
    def test_verify_all_artifacts_exist(self, root: Path, delivery_artifacts: dict):
        artifacts = verify_delivery_artifacts_for_closure(str(root))
        assert len(artifacts) == len(DELIVERY_ARTIFACTS)

    def test_verify_all_required_exist(self, root: Path, delivery_artifacts: dict):
        artifacts = verify_delivery_artifacts_for_closure(str(root))
        required_missing = [a for a in artifacts if a["required"] and not a["exists"]]
        assert len(required_missing) == 0

    def test_verify_sha256_computed(self, root: Path, delivery_artifacts: dict):
        artifacts = verify_delivery_artifacts_for_closure(str(root))
        existing = [a for a in artifacts if a["exists"]]
        for art in existing:
            assert art["sha256"] is not None
            assert len(art["sha256"]) == 64

    def test_verify_missing_artifacts(self, root: Path):
        artifacts = verify_delivery_artifacts_for_closure(str(root))
        missing = [a for a in artifacts if not a["exists"]]
        assert len(missing) == len(DELIVERY_ARTIFACTS)
        for art in missing:
            assert len(art["validation_errors"]) > 0


class TestBuildDeliveryClosureChecks:
    def test_checks_structure(self, root: Path, delivery_artifacts: dict, stage_reports: None):
        finalization_state = load_delivery_finalization_state(str(root))
        artifact_summary = verify_delivery_artifacts_for_closure(str(root))
        stage_chain = collect_foundation_ci_delivery_stage_chain(str(root))
        mutation_guard = _safe_baseline(str(root))
        checks = build_delivery_closure_checks(
            stage_chain, artifact_summary, finalization_state, mutation_guard, str(root)
        )
        assert len(checks) > 0
        for check in checks:
            assert "check_id" in check
            assert "domain" in check
            assert "passed" in check
            assert "status" in check
            assert "risk_level" in check

    def test_chain_completeness_check(
        self, root: Path, delivery_artifacts: dict, stage_reports: None
    ):
        finalization_state = load_delivery_finalization_state(str(root))
        artifact_summary = verify_delivery_artifacts_for_closure(str(root))
        stage_chain = collect_foundation_ci_delivery_stage_chain(str(root))
        mutation_guard = _safe_baseline(str(root))
        checks = build_delivery_closure_checks(
            stage_chain, artifact_summary, finalization_state, mutation_guard, str(root)
        )
        chain_checks = [c for c in checks if c["domain"] == DeliveryClosureDomain.CHAIN_COMPLETENESS.value]
        assert len(chain_checks) >= 2

    def test_artifact_integrity_check(
        self, root: Path, delivery_artifacts: dict, stage_reports: None
    ):
        finalization_state = load_delivery_finalization_state(str(root))
        artifact_summary = verify_delivery_artifacts_for_closure(str(root))
        stage_chain = collect_foundation_ci_delivery_stage_chain(str(root))
        mutation_guard = _safe_baseline(str(root))
        checks = build_delivery_closure_checks(
            stage_chain, artifact_summary, finalization_state, mutation_guard, str(root)
        )
        integrity_checks = [c for c in checks if c["domain"] == DeliveryClosureDomain.ARTIFACT_INTEGRITY.value]
        assert len(integrity_checks) > 0

    def test_delivery_package_check(self, root: Path, delivery_artifacts: dict, stage_reports: None):
        finalization_state = load_delivery_finalization_state(str(root))
        artifact_summary = verify_delivery_artifacts_for_closure(str(root))
        stage_chain = collect_foundation_ci_delivery_stage_chain(str(root))
        mutation_guard = _safe_baseline(str(root))
        checks = build_delivery_closure_checks(
            stage_chain, artifact_summary, finalization_state, mutation_guard, str(root)
        )
        dp_checks = [c for c in checks if c["domain"] == DeliveryClosureDomain.DELIVERY_PACKAGE.value]
        assert len(dp_checks) >= 3

    def test_mutation_guard_checks(self, root: Path, delivery_artifacts: dict):
        finalization_state = load_delivery_finalization_state(str(root))
        artifact_summary = verify_delivery_artifacts_for_closure(str(root))
        stage_chain = []
        mutation_guard = _safe_baseline(str(root))
        checks = build_delivery_closure_checks(
            stage_chain, artifact_summary, finalization_state, mutation_guard, str(root)
        )
        mg_checks = [c for c in checks if c["domain"] == DeliveryClosureDomain.MUTATION_GUARD.value]
        assert len(mg_checks) >= 3

    def test_checks_sorted(self, root: Path, delivery_artifacts: dict, stage_reports: None):
        finalization_state = load_delivery_finalization_state(str(root))
        artifact_summary = verify_delivery_artifacts_for_closure(str(root))
        stage_chain = collect_foundation_ci_delivery_stage_chain(str(root))
        mutation_guard = _safe_baseline(str(root))
        checks = build_delivery_closure_checks(
            stage_chain, artifact_summary, finalization_state, mutation_guard, str(root)
        )
        passed_idx = next((i for i, c in enumerate(checks) if not c["passed"]), len(checks))
        for i in range(passed_idx):
            assert checks[i]["passed"] is True


class TestBuildReceiverNextSteps:
    def test_next_steps_when_all_passed(self):
        passed_checks = [
            {"check_id": "c1", "domain": "mutation_guard", "passed": True, "status": "passed",
             "risk_level": "low", "description": "c1", "recommendations": []},
        ]
        finalization_state = {"exists": True, "data": {"status": "finalized"}}
        artifact_summary = [{"filename": "f1", "role": "patch", "exists": True,
                            "required": True, "validation_errors": []}]
        steps = build_receiver_next_steps(passed_checks, finalization_state, artifact_summary)
        assert len(steps) > 0
        assert "passed" in " ".join(steps).lower()

    def test_next_steps_for_missing_artifacts(self):
        failed_checks = [
            {"check_id": "artifact_required_exist", "domain": "artifact_integrity",
             "passed": False, "status": "failed", "risk_level": "critical",
             "description": "Required artifact missing", "recommendations": ["Restore artifact"]},
        ]
        artifact_summary = [
            {"filename": "missing.patch", "role": "patch", "exists": False,
             "required": True, "validation_errors": ["Missing"]},
        ]
        steps = build_receiver_next_steps(
            failed_checks,
            {"exists": True, "data": {}},
            artifact_summary,
        )
        assert len(steps) > 0

    def test_next_steps_for_mutation_guard_failure(self):
        failed_checks = [
            {"check_id": "mutation_no_staged", "domain": "mutation_guard",
             "passed": False, "status": "failed", "risk_level": "high",
             "description": "Staged changes detected", "recommendations": ["Unstage"]},
        ]
        steps = build_receiver_next_steps(
            failed_checks,
            {"exists": True, "data": {}},
            [],
        )
        assert any("unstage" in s.lower() for s in steps)


class TestVerifyNoMutationDuringClosureReview:
    def test_no_mutation_when_clean(self, root: Path):
        baseline = _safe_baseline(str(root))
        result = verify_no_mutation_during_closure_review(baseline, str(root))
        assert result["mutated"] is False

    def test_detects_staged_change(self, root: Path):
        baseline = _safe_baseline(str(root))
        (root / "new_file.txt").write_text("new", encoding="utf-8")
        subprocess.run(["git", "add", "new_file.txt"], cwd=str(root), capture_output=True, shell=False)
        result = verify_no_mutation_during_closure_review(baseline, str(root))
        assert result["mutated"] is True
        assert result["details"]["staged_changed"] is True


class TestEvaluateFoundationCiDeliveryClosure:
    def test_evaluate_returns_review_object(self, root: Path, delivery_artifacts: dict, stage_reports: None):
        review = evaluate_foundation_ci_delivery_closure(str(root))
        assert isinstance(review, DeliveryClosureReview)
        assert review.review_id == "R241-16V"
        assert review.status in [s.value for s in DeliveryClosureStatus]
        assert review.decision in [d.value for d in DeliveryClosureDecision]

    def test_evaluate_with_all_artifacts_and_reports(
        self, root: Path, delivery_artifacts: dict, stage_reports: None
    ):
        review = evaluate_foundation_ci_delivery_closure(str(root))
        assert review.status in (
            DeliveryClosureStatus.PASSED.value,
            DeliveryClosureStatus.PASSED_WITH_WARNINGS.value,
        )

    def test_evaluate_with_no_artifacts(self, root: Path):
        review = evaluate_foundation_ci_delivery_closure(str(root))
        assert review.status == DeliveryClosureStatus.FAILED.value
        assert review.decision == DeliveryClosureDecision.BLOCK_CLOSURE.value


class TestValidateDeliveryClosureReview:
    def test_validate_valid_review(self, root: Path, delivery_artifacts: dict, stage_reports: None):
        review = evaluate_foundation_ci_delivery_closure(str(root))
        validation = validate_delivery_closure_review(review)
        assert validation["valid"] is True
        assert len(validation["errors"]) == 0

    def test_validate_empty_review(self):
        review = DeliveryClosureReview(
            review_id="",
            stage_chain=[],
            artifact_summary=[],
            closure_checks=[],
            receiver_next_steps=[],
            mutation_guard={},
            decision="unknown",
            status="unknown",
            risk_level="unknown",
            generated_at="",
        )
        validation = validate_delivery_closure_review(review)
        assert validation["valid"] is False
        assert len(validation["errors"]) > 0

    def test_validate_missing_stage_id(self):
        review = DeliveryClosureReview(
            review_id="R241-16V",
            stage_chain=[{"description": "no stage_id"}],
            artifact_summary=[],
            closure_checks=[],
            receiver_next_steps=[],
            mutation_guard={},
            decision=DeliveryClosureDecision.APPROVE_CLOSURE.value,
            status=DeliveryClosureStatus.PASSED.value,
            risk_level=DeliveryClosureRiskLevel.LOW.value,
            generated_at=_now(),
        )
        validation = validate_delivery_closure_review(review)
        assert validation["valid"] is False

    def test_validate_missing_check_id(self):
        review = DeliveryClosureReview(
            review_id="R241-16V",
            stage_chain=[],
            artifact_summary=[],
            closure_checks=[{"description": "no check_id", "passed": True, "status": "passed", "risk_level": "low", "domain": "test"}],
            receiver_next_steps=[],
            mutation_guard={},
            decision=DeliveryClosureDecision.APPROVE_CLOSURE.value,
            status=DeliveryClosureStatus.PASSED.value,
            risk_level=DeliveryClosureRiskLevel.LOW.value,
            generated_at=_now(),
        )
        validation = validate_delivery_closure_review(review)
        assert validation["valid"] is False

    def test_validate_warnings_for_passed_with_errors(self):
        review = DeliveryClosureReview(
            review_id="R241-16V",
            stage_chain=[],
            artifact_summary=[],
            closure_checks=[],
            receiver_next_steps=[],
            mutation_guard={},
            decision=DeliveryClosureDecision.APPROVE_CLOSURE.value,
            status=DeliveryClosureStatus.PASSED.value,
            risk_level=DeliveryClosureRiskLevel.LOW.value,
            generated_at="",
            validated=False,
            validation_errors=["Error 1"],
        )
        validation = validate_delivery_closure_review(review)
        assert validation["valid"] is False
        assert len(validation["warnings"]) > 0


class TestGenerateDeliveryClosureReviewReport:
    def test_generates_json_and_md(self, root: Path, delivery_artifacts: dict, stage_reports: None):
        review = evaluate_foundation_ci_delivery_closure(str(root))
        paths = generate_delivery_closure_review_report(review, str(root))
        assert "json_path" in paths
        assert "md_path" in paths
        json_path = Path(paths["json_path"])
        md_path = Path(paths["md_path"])
        assert json_path.exists()
        assert md_path.exists()

    def test_json_content_valid(self, root: Path, delivery_artifacts: dict, stage_reports: None):
        review = evaluate_foundation_ci_delivery_closure(str(root))
        paths = generate_delivery_closure_review_report(review, str(root))
        json_path = Path(paths["json_path"])
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["review_id"] == "R241-16V"
        assert "stage_chain" in data
        assert "artifact_summary" in data
        assert "closure_checks" in data

    def test_md_content_valid(self, root: Path, delivery_artifacts: dict, stage_reports: None):
        review = evaluate_foundation_ci_delivery_closure(str(root))
        paths = generate_delivery_closure_review_report(review, str(root))
        md_path = Path(paths["md_path"])
        content = md_path.read_text(encoding="utf-8")
        assert "Foundation CI Delivery Closure Review" in content
        assert "R241-16V" in content
        assert "Stage Chain" in content
        assert "Closure Checks" in content

    def test_md_no_patch_content(self, root: Path, delivery_artifacts: dict, stage_reports: None):
        review = evaluate_foundation_ci_delivery_closure(str(root))
        paths = generate_delivery_closure_review_report(review, str(root))
        md_path = Path(paths["md_path"])
        content = md_path.read_text(encoding="utf-8")
        assert "patch content" not in content.lower()

    def test_report_contains_mutation_guard(self, root: Path, delivery_artifacts: dict, stage_reports: None):
        review = evaluate_foundation_ci_delivery_closure(str(root))
        paths = generate_delivery_closure_review_report(review, str(root))
        json_path = Path(paths["json_path"])
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert "mutation_guard" in data
        mg = data["mutation_guard"]
        assert "head_hash" in mg
        assert "staged_files" in mg

    def test_report_contains_receiver_next_steps(
        self, root: Path, delivery_artifacts: dict, stage_reports: None
    ):
        review = evaluate_foundation_ci_delivery_closure(str(root))
        paths = generate_delivery_closure_review_report(review, str(root))
        md_path = Path(paths["md_path"])
        content = md_path.read_text(encoding="utf-8")
        assert "Receiver Next Steps" in content or "Next Steps" in content


class TestIntegration:
    def test_full_closure_review_pipeline(
        self, root: Path, delivery_artifacts: dict, stage_reports: None
    ):
        review = evaluate_foundation_ci_delivery_closure(str(root))
        validation = validate_delivery_closure_review(review)
        assert validation["valid"] is True
        paths = generate_delivery_closure_review_report(review, str(root))
        assert Path(paths["json_path"]).exists()
        assert Path(paths["md_path"]).exists()

    def test_full_closure_review_pipeline_from_scratch(self, root: Path):
        review = evaluate_foundation_ci_delivery_closure(str(root))
        validation = validate_delivery_closure_review(review)
        paths = generate_delivery_closure_review_report(review, str(root))
        json_path = Path(paths["json_path"])
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["status"] == DeliveryClosureStatus.FAILED.value
        assert data["decision"] == DeliveryClosureDecision.BLOCK_CLOSURE.value
        assert len(data["receiver_next_steps"]) > 0

    def test_crosscheck_sha_match(
        self, root: Path, delivery_artifacts: dict, stage_reports: None
    ):
        finalization_state = load_delivery_finalization_state(str(root))
        artifact_summary = verify_delivery_artifacts_for_closure(str(root))
        stage_chain = collect_foundation_ci_delivery_stage_chain(str(root))
        mutation_guard = _safe_baseline(str(root))
        checks = build_delivery_closure_checks(
            stage_chain, artifact_summary, finalization_state, mutation_guard, str(root)
        )
        sha_check = next(
            (c for c in checks if c["check_id"] == "crosscheck_manifest_verification_sha"),
            None
        )
        if sha_check:
            assert sha_check["passed"] is True
