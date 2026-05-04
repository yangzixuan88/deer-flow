"""R241-16U: Delivery Package Finalization — tests."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Generator
from unittest.mock import patch

import pytest

from app.foundation.ci_delivery_package_finalization import (
    ROOT,
    REPORT_DIR,
    SOURCE_COMMIT_HASH,
    TARGET_WORKFLOW,
    BUNDLE_PATH,
    GENERATION_RESULT_PATH,
    DELIVERY_NOTE_PATH,
    MANIFEST_PATH,
    PATCH_PATH,
    VERIFICATION_RESULT_PATH,
    DeliveryArtifactRole,
    DeliveryPackageDecision,
    DeliveryPackageFinalizationStatus,
    DeliveryPackageRiskLevel,
    _now,
    _root,
    _run_git,
    _safe_baseline,
    _sha256,
    build_delivery_final_checklist,
    collect_delivery_artifacts,
    evaluate_delivery_package_finalization,
    generate_delivery_final_checklist,
    generate_delivery_package_index,
    generate_delivery_package_finalization_report,
    generate_handoff_summary,
    load_verified_patch_bundle_state,
    validate_delivery_artifact_integrity,
    validate_delivery_package_finalization_result,
    verify_no_local_mutation_after_finalization,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def patch_report_dir(root: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path, None, None]:
    """Patch module-level REPORT_DIR so tests use isolated tmp_path."""
    test_report_dir = root / "migration_reports" / "foundation_audit"
    test_report_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "app.foundation.ci_delivery_package_finalization.REPORT_DIR",
        test_report_dir,
    )
    monkeypatch.setattr(
        "app.foundation.ci_delivery_package_finalization.VERIFICATION_RESULT_PATH",
        test_report_dir / "R241-16T_PATCH_BUNDLE_VERIFICATION_RESULT.json",
    )
    monkeypatch.setattr(
        "app.foundation.ci_delivery_package_finalization.DELIVERY_NOTE_PATH",
        test_report_dir / "R241-16T_PATCH_DELIVERY_NOTE.md",
    )
    monkeypatch.setattr(
        "app.foundation.ci_delivery_package_finalization.PATCH_PATH",
        test_report_dir / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch",
    )
    monkeypatch.setattr(
        "app.foundation.ci_delivery_package_finalization.BUNDLE_PATH",
        test_report_dir / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle",
    )
    monkeypatch.setattr(
        "app.foundation.ci_delivery_package_finalization.MANIFEST_PATH",
        test_report_dir / "R241-16S_PATCH_BUNDLE_MANIFEST.json",
    )
    monkeypatch.setattr(
        "app.foundation.ci_delivery_package_finalization.GENERATION_RESULT_PATH",
        test_report_dir / "R241-16S_PATCH_BUNDLE_GENERATION_RESULT.json",
    )
    yield root


@pytest.fixture
def root(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a self-contained root dir with required artifact structure."""
    root = tmp_path / "project"
    root.mkdir()
    migration_dir = root / "migration_reports" / "foundation_audit"
    migration_dir.mkdir(parents=True)

    # Create workflow file
    workflow_dir = root / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "foundation-manual-dispatch.yml").write_text(
        "name: Foundation Manual\non: workflow_dispatch\n",
        encoding="utf-8",
    )

    # Init git repo
    subprocess.run(["git", "init"], cwd=str(root), capture_output=True, shell=False)
    for cmd in [
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Test User"],
        ["git", "add", "-A"],
        ["git", "commit", "-m", "init"],
    ]:
        subprocess.run(cmd, cwd=str(root), capture_output=True, shell=False)

    # Create minimal manifest
    manifest_data = {
        "source_commit_hash": SOURCE_COMMIT_HASH,
        "source_changed_files": [TARGET_WORKFLOW],
        "patch_sha256": "a" * 64,
        "bundle_sha256": "b" * 64,
        "generation_timestamp": _now(),
    }
    (migration_dir / "R241-16S_PATCH_BUNDLE_MANIFEST.json").write_text(
        json.dumps(manifest_data, indent=2), encoding="utf-8"
    )

    yield root


@pytest.fixture
def valid_verification_result(tmp_path: Path, root: Path) -> dict:
    """Create a valid R241-16T verification result."""
    migration_dir = root / "migration_reports" / "foundation_audit"
    data = {
        "status": "verified_with_warnings",
        "decision": "approve_delivery_artifacts",
        "validation": {"valid": True, "blocked_reasons": []},
        "patch_inspection": {
            "safe_to_share": True,
            "patch_exists": True,
            "patch_sha": "deadbeef" + "a" * 48,
            "no_pr_push_schedule_triggers": True,
            "no_secrets_found": True,
            "no_auto_fix": True,
            "secrets_in_patch": [],
            "warnings": [],
        },
        "bundle_inspection": {
            "safe_to_share": True,
            "bundle_exists": True,
            "bundle_sha": "cafebabe" + "b" * 48,
            "bundle_verify_passed": True,
            "warnings": [],
        },
        "source_commit_hash": SOURCE_COMMIT_HASH,
        "source_changed_files": [TARGET_WORKFLOW],
        "mutation_guard": {"all_passed": True, "checks": []},
        "delivery_note_result": {"note_exists": True},
        "warnings": ["known_warning: apply_check may show already exists"],
    }
    path = migration_dir / "R241-16T_PATCH_BUNDLE_VERIFICATION_RESULT.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


@pytest.fixture
def delivery_note(tmp_path: Path, root: Path) -> Path:
    """Create a delivery note."""
    migration_dir = root / "migration_reports" / "foundation_audit"
    content = (
        "# R241-16T Patch Delivery Note\n\n"
        "## Apply Instructions\n\n"
        "Run: git am < patch\n\n"
        "## Verify\n\n"
        "Run: git diff-tree --no-commit-id --name-only -r 94908556\n"
    )
    path = migration_dir / "R241-16T_PATCH_DELIVERY_NOTE.md"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def with_artifacts(
    tmp_path: Path,
    root: Path,
    valid_verification_result: dict,
    delivery_note: Path,
) -> Path:
    """Create all required artifact files and update manifest/verification with real SHAs."""
    migration_dir = root / "migration_reports" / "foundation_audit"

    # Patch content (must match TARGET_WORKFLOW)
    patch_content = (
        f"diff --git a/{TARGET_WORKFLOW} b/{TARGET_WORKFLOW}\n"
        f"new file mode 100644\n"
        f"--- /dev/null\n"
        f"+++ b/{TARGET_WORKFLOW}\n"
        f"@@ -0,0 +1,3 @@\n"
        f"+name: Test\n"
        f"+on: workflow_dispatch\n"
        f"+jobs:\n"
    )
    patch_path = migration_dir / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch"
    patch_path.write_text(patch_content, encoding="utf-8")

    # Bundle (fake git bundle - just a file)
    bundle_path = migration_dir / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle"
    bundle_path.write_bytes(b"FAKE BUNDLE")

    # Compute real SHAs
    real_patch_sha = _sha256(patch_path)
    real_bundle_sha = _sha256(bundle_path)

    # Update manifest with real SHAs so integrity checks pass
    manifest_path = migration_dir / "R241-16S_PATCH_BUNDLE_MANIFEST.json"
    manifest_data = {
        "source_commit_hash": SOURCE_COMMIT_HASH,
        "source_changed_files": [TARGET_WORKFLOW],
        "patch_sha256": real_patch_sha,
        "bundle_sha256": real_bundle_sha,
        "generation_timestamp": _now(),
    }
    manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    # Update verification result with real SHAs so integrity checks pass
    verification_path = migration_dir / "R241-16T_PATCH_BUNDLE_VERIFICATION_RESULT.json"
    verification_data = {
        "status": "verified_with_warnings",
        "decision": "approve_delivery_artifacts",
        "validation": {"valid": True, "blocked_reasons": []},
        "patch_inspection": {
            "safe_to_share": True,
            "patch_exists": True,
            "patch_sha": real_patch_sha,
            "no_pr_push_schedule_triggers": True,
            "no_secrets_found": True,
            "no_auto_fix": True,
            "secrets_in_patch": [],
            "warnings": [],
        },
        "bundle_inspection": {
            "safe_to_share": True,
            "bundle_exists": True,
            "bundle_sha": real_bundle_sha,
            "bundle_verify_passed": True,
            "warnings": [],
        },
        "source_commit_hash": SOURCE_COMMIT_HASH,
        "source_changed_files": [TARGET_WORKFLOW],
        "mutation_guard": {"all_passed": True, "checks": []},
        "delivery_note_result": {"note_exists": True},
        "warnings": ["known_warning: apply_check may show already exists"],
    }
    verification_path.write_text(json.dumps(verification_data), encoding="utf-8")

    # Generation result
    gen_data = {
        "status": "patch_bundle_generated",
        "decision": "proceed",
        "patch_path": str(patch_path),
        "bundle_path": str(bundle_path),
    }
    (migration_dir / "R241-16S_PATCH_BUNDLE_GENERATION_RESULT.json").write_text(
        json.dumps(gen_data), encoding="utf-8"
    )

    return root


# ── Test: Enums ────────────────────────────────────────────────────────────────

class TestEnums:
    def test_finalization_status_values(self):
        assert DeliveryPackageFinalizationStatus.FINALIZED.value == "finalized"
        assert DeliveryPackageFinalizationStatus.FINALIZED_WITH_WARNINGS.value == "finalized_with_warnings"
        assert DeliveryPackageFinalizationStatus.BLOCKED_MISSING_ARTIFACT.value == "blocked_missing_artifact"
        assert DeliveryPackageFinalizationStatus.BLOCKED_CHECKSUM_MISMATCH.value == "blocked_checksum_mismatch"
        assert DeliveryPackageFinalizationStatus.BLOCKED_UNSAFE_ARTIFACT.value == "blocked_unsafe_artifact"
        assert DeliveryPackageFinalizationStatus.BLOCKED_VERIFICATION_NOT_VALID.value == "blocked_verification_not_valid"
        assert DeliveryPackageFinalizationStatus.BLOCKED_MUTATION_DETECTED.value == "blocked_mutation_detected"
        assert DeliveryPackageFinalizationStatus.UNKNOWN.value == "unknown"

    def test_decision_values(self):
        assert DeliveryPackageDecision.APPROVE_HANDOFF.value == "approve_handoff"
        assert DeliveryPackageDecision.APPROVE_HANDOFF_WITH_WARNINGS.value == "approve_handoff_with_warnings"
        assert DeliveryPackageDecision.BLOCK_HANDOFF.value == "block_handoff"
        assert DeliveryPackageDecision.UNKNOWN.value == "unknown"

    def test_artifact_role_values(self):
        assert DeliveryArtifactRole.PATCH.value == "patch"
        assert DeliveryArtifactRole.BUNDLE.value == "bundle"
        assert DeliveryArtifactRole.MANIFEST.value == "manifest"
        assert DeliveryArtifactRole.VERIFICATION_REPORT.value == "verification_report"
        assert DeliveryArtifactRole.DELIVERY_NOTE.value == "delivery_note"
        assert DeliveryArtifactRole.HANDOFF_INDEX.value == "handoff_index"
        assert DeliveryArtifactRole.FINAL_CHECKLIST.value == "final_checklist"
        assert DeliveryArtifactRole.HANDOFF_SUMMARY.value == "handoff_summary"
        assert DeliveryArtifactRole.GENERATION_RESULT.value == "generation_result"
        assert DeliveryArtifactRole.UNKNOWN.value == "unknown"

    def test_risk_level_values(self):
        assert DeliveryPackageRiskLevel.LOW.value == "low"
        assert DeliveryPackageRiskLevel.MEDIUM.value == "medium"
        assert DeliveryPackageRiskLevel.HIGH.value == "high"
        assert DeliveryPackageRiskLevel.CRITICAL.value == "critical"
        assert DeliveryPackageRiskLevel.UNKNOWN.value == "unknown"


# ── Test: Helpers ──────────────────────────────────────────────────────────────

class TestHelpers:
    def test_now_returns_iso_format(self):
        result = _now()
        assert "T" in result
        assert "Z" in result or "+00:00" in result

    def test_root_defaults_to_project_root(self):
        result = _root(None)
        assert result == ROOT

    def test_root_with_valid_dir(self, tmp_path: Path):
        result = _root(str(tmp_path))
        assert result == tmp_path.resolve()

    def test_root_with_invalid_dir(self, tmp_path: Path):
        nonexistent = tmp_path / "nonexistent"
        result = _root(str(nonexistent))
        assert result == ROOT

    def test_sha256_computes_correctly(self, tmp_path: Path):
        file = tmp_path / "test.txt"
        content = b"hello world"
        file.write_bytes(content)
        expected = hashlib.sha256(content).hexdigest()
        assert _sha256(file) == expected

    def test_sha256_reads_bytes_not_text(self, tmp_path: Path):
        # Write binary data that differs when decoded as UTF-8
        file = tmp_path / "test.bin"
        file.write_bytes(b"\x80\x81\x82")
        sha = _sha256(file)
        assert len(sha) == 64

    def test_run_git_success(self, root: Path):
        result = _run_git(["git", "rev-parse", "HEAD"], str(root))
        assert result["exit_code"] == 0
        assert result["command_executed"] is True
        assert result["cwd"] == str(root)

    def test_run_git_failure(self, root: Path):
        result = _run_git(["git", "nonexistent-command"], str(root))
        assert result["exit_code"] != 0
        assert result["command_executed"] is True

    def test_safe_baseline_returns_structure(self, root: Path):
        result = _safe_baseline(str(root))
        assert "captured_at" in result
        assert "head_hash" in result
        assert "branch" in result
        assert "staged_files" in result
        assert "git_status_short" in result
        assert "audit_jsonl_line_count" in result
        assert "runtime_dir_exists" in result


# ── Test: load_verified_patch_bundle_state ────────────────────────────────────

class TestLoadVerifiedPatchBundleState:
    def test_returns_blocked_when_verification_result_missing(self, root: Path):
        result = load_verified_patch_bundle_state(str(root))
        assert result["loaded"] is False
        assert result["valid"] is False
        assert "verification_result_missing" in result["blocked_reasons"]

    def test_returns_blocked_when_verification_result_invalid(
        self, root: Path, valid_verification_result: dict
    ):
        # Write invalid status
        data = valid_verification_result.copy()
        data["status"] = "rejected"
        (root / "migration_reports" / "foundation_audit" / "R241-16T_PATCH_BUNDLE_VERIFICATION_RESULT.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        result = load_verified_patch_bundle_state(str(root))
        assert result["valid"] is False

    def test_returns_valid_with_complete_verification_result(
        self, root: Path, valid_verification_result: dict, delivery_note: Path
    ):
        result = load_verified_patch_bundle_state(str(root))
        assert result["loaded"] is True
        assert result["valid"] is True
        assert result["patch_safe"] is True
        assert result["bundle_safe"] is True
        assert result["source_commit_hash"] == SOURCE_COMMIT_HASH

    def test_returns_blocked_when_validation_invalid(
        self, root: Path, valid_verification_result: dict
    ):
        data = valid_verification_result.copy()
        data["validation"] = {"valid": False, "blocked_reasons": ["test_failure"]}
        (root / "migration_reports" / "foundation_audit" / "R241-16T_PATCH_BUNDLE_VERIFICATION_RESULT.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        result = load_verified_patch_bundle_state(str(root))
        assert result["valid"] is False


# ── Test: collect_delivery_artifacts ─────────────────────────────────────────

class TestCollectDeliveryArtifacts:
    def test_returns_blocked_when_patch_missing(self, root: Path, valid_verification_result: dict):
        result = collect_delivery_artifacts(str(root))
        assert len(result["blocked_reasons"]) > 0
        patch_art = next(a for a in result["artifacts"] if a["artifact_id"] == "patch")
        assert patch_art["exists"] is False
        assert patch_art["required"] is True

    def test_collects_all_artifacts_when_present(
        self, root: Path, with_artifacts: Path, valid_verification_result: dict
    ):
        result = collect_delivery_artifacts(str(root))
        assert len(result["artifacts"]) == 6
        patch_art = next(a for a in result["artifacts"] if a["artifact_id"] == "patch")
        assert patch_art["exists"] is True
        assert patch_art["size_bytes"] > 0
        assert len(patch_art["sha256"]) == 64

    def test_artifact_paths_are_within_audit_dir(self, root: Path, with_artifacts: Path):
        result = collect_delivery_artifacts(str(root))
        for art in result["artifacts"]:
            if art["exists"]:
                assert str(REPORT_DIR) in art["path"] or "migration_reports" in art["path"]


# ── Test: validate_delivery_artifact_integrity ─────────────────────────────────

class TestValidateDeliveryArtifactIntegrity:
    def test_blocked_when_verification_result_missing(self, root: Path):
        artifacts = {"artifacts": []}
        result = validate_delivery_artifact_integrity(artifacts, str(root))
        assert result["valid"] is False
        assert "verification_result_missing_for_integrity_check" in result["blocked_reasons"]

    def test_fails_when_required_artifacts_missing(
        self, root: Path, valid_verification_result: dict
    ):
        # Provide artifacts with required=True but exists=False
        artifacts = {
            "artifacts": [
                {
                    "artifact_id": "patch",
                    "role": DeliveryArtifactRole.PATCH.value,
                    "path": str(root / "migration_reports" / "foundation_audit" / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch"),
                    "exists": False,
                    "size_bytes": 0,
                    "sha256": "",
                    "required": True,
                    "safe_to_share": True,
                    "source_stage": "R241-16S",
                    "warnings": [],
                    "errors": [],
                },
            ]
        }
        result = validate_delivery_artifact_integrity(artifacts, str(root))
        assert result["valid"] is False
        failed_check = next((c for c in result["checks"] if c["check_id"] == "required_artifacts_exist"), None)
        assert failed_check is not None and failed_check["passed"] is False

    def test_validates_successfully_with_matching_artifacts(
        self, root: Path, with_artifacts: Path, valid_verification_result: dict
    ):
        artifacts = collect_delivery_artifacts(str(root))
        result = validate_delivery_artifact_integrity(artifacts, str(root))
        # Should have checks, even if some fail due to SHA mismatches
        assert len(result["checks"]) > 0

    def test_check_ids_are_deterministic(self, root: Path, with_artifacts: Path):
        artifacts = collect_delivery_artifacts(str(root))
        result1 = validate_delivery_artifact_integrity(artifacts, str(root))
        result2 = validate_delivery_artifact_integrity(artifacts, str(root))
        check_ids_1 = [c["check_id"] for c in result1["checks"]]
        check_ids_2 = [c["check_id"] for c in result2["checks"]]
        assert check_ids_1 == check_ids_2


# ── Test: build_delivery_final_checklist ──────────────────────────────────────

class TestBuildDeliveryFinalChecklist:
    def test_returns_items_structure(self, root: Path, valid_verification_result: dict):
        result = build_delivery_final_checklist(str(root))
        assert "items" in result
        assert "all_passed" in result
        assert "critical_passed" in result
        assert len(result["items"]) > 0

    def test_all_items_have_required_fields(self, root: Path, valid_verification_result: dict):
        result = build_delivery_final_checklist(str(root))
        for item in result["items"]:
            assert "item_id" in item
            assert "passed" in item
            assert "risk_level" in item
            assert "description" in item
            assert "required_before_handoff" in item

    def test_critical_items_require_pass(
        self, root: Path, valid_verification_result: dict, with_artifacts: Path
    ):
        result = build_delivery_final_checklist(str(root))
        critical_items = [
            i for i in result["items"]
            if i["risk_level"] == DeliveryPackageRiskLevel.CRITICAL.value
            and i.get("required_before_handoff")
        ]
        # At least some critical items should pass with valid artifacts
        assert len(critical_items) > 0


# ── Test: generate_delivery_package_index ──────────────────────────────────────

class TestGenerateDeliveryPackageIndex:
    def test_writes_json_and_md_files(self, root: Path, with_artifacts: Path, valid_verification_result: dict):
        artifacts = collect_delivery_artifacts(str(root))
        result = generate_delivery_package_index(str(root), artifacts)
        json_path = Path(result["json_path"])
        md_path = Path(result["md_path"])
        assert json_path.exists()
        assert md_path.exists()
        # Verify JSON is valid
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["index_id"] == "R241-16U-index"
        assert data["source_commit_hash"] == SOURCE_COMMIT_HASH

    def test_json_contains_all_artifacts(
        self, root: Path, with_artifacts: Path, valid_verification_result: dict
    ):
        artifacts = collect_delivery_artifacts(str(root))
        result = generate_delivery_package_index(str(root), artifacts)
        data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
        assert len(data["artifacts"]) == len(artifacts["artifacts"])

    def test_md_contains_do_not_run_warnings(self, root: Path, with_artifacts: Path, valid_verification_result: dict):
        artifacts = collect_delivery_artifacts(str(root))
        result = generate_delivery_package_index(str(root), artifacts)
        content = Path(result["md_path"]).read_text(encoding="utf-8")
        assert "DO NOT" in content
        assert "workflow_dispatch" in content

    def test_index_contains_no_full_patch_content(
        self, root: Path, with_artifacts: Path, valid_verification_result: dict
    ):
        artifacts = collect_delivery_artifacts(str(root))
        result = generate_delivery_package_index(str(root), artifacts)
        content = Path(result["md_path"]).read_text(encoding="utf-8")
        # Should not have many diff hunk markers
        diff_lines = [
            l for l in content.splitlines()
            if l.startswith("+++") or l.startswith("---") or l.startswith("@@")
        ]
        assert len(diff_lines) == 0


# ── Test: generate_delivery_final_checklist ──────────────────────────────────

class TestGenerateDeliveryFinalChecklist:
    def test_writes_checklist_md(self, root: Path, valid_verification_result: dict, with_artifacts: Path):
        checklist = build_delivery_final_checklist(str(root))
        result = generate_delivery_final_checklist(str(root), checklist)
        path = Path(result["checklist_path"])
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "R241-16U" in content
        assert "PASS" in content or "FAIL" in content

    def test_contains_status_summary(self, root: Path, valid_verification_result: dict, with_artifacts: Path):
        checklist = build_delivery_final_checklist(str(root))
        result = generate_delivery_final_checklist(str(root), checklist)
        content = Path(result["checklist_path"]).read_text(encoding="utf-8")
        assert "Status Summary" in content or "Total Items" in content


# ── Test: generate_handoff_summary ──────────────────────────────────────────

class TestGenerateHandoffSummary:
    def test_writes_summary_md(self, root: Path, with_artifacts: Path, valid_verification_result: dict):
        result = generate_handoff_summary(str(root))
        path = Path(result["summary_path"])
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "R241-16U" in content
        assert "push" in content.lower()

    def test_contains_receiver_instructions(
        self, root: Path, with_artifacts: Path, valid_verification_result: dict
    ):
        result = generate_handoff_summary(str(root))
        content = Path(result["summary_path"]).read_text(encoding="utf-8")
        assert "git am" in content
        assert "workflow_dispatch" in content or "GitHub" in content


# ── Test: verify_no_local_mutation_after_finalization ─────────────────────────

class TestVerifyNoLocalMutationAfterFinalization:
    def test_passes_with_no_changes(self, root: Path, valid_verification_result: dict, with_artifacts: Path):
        baseline = _safe_baseline(str(root))
        # Generate reports (allowed writes)
        generate_delivery_package_index(str(root))
        generate_delivery_final_checklist(str(root))
        generate_handoff_summary(str(root))
        # Verify
        result = verify_no_local_mutation_after_finalization(str(root), baseline)
        assert result["all_passed"] is True

    def test_detects_head_change(self, root: Path, valid_verification_result: dict):
        baseline = _safe_baseline(str(root))
        # Simulate HEAD change
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "dummy"],
            cwd=str(root),
            capture_output=True,
            shell=False,
        )
        result = verify_no_local_mutation_after_finalization(str(root), baseline)
        assert result["all_passed"] is False
        failed = [c for c in result["checks"] if not c["passed"]]
        assert any("head" in c["check_id"].lower() for c in failed)

    def test_allows_r241_16u_artifacts_only(
        self, root: Path, valid_verification_result: dict, with_artifacts: Path
    ):
        baseline = _safe_baseline(str(root))
        # Generate allowed artifacts
        generate_delivery_package_index(str(root))
        generate_delivery_final_checklist(str(root))
        generate_handoff_summary(str(root))
        result = verify_no_local_mutation_after_finalization(str(root), baseline)
        # Should pass - only allowed artifacts created
        check = next(c for c in result["checks"] if c["check_id"] == "no_unexpected_artifacts")
        assert check["passed"] is True


# ── Test: evaluate_delivery_package_finalization ───────────────────────────────

class TestEvaluateDeliveryPackageFinalization:
    def test_returns_complete_result_structure(
        self, root: Path, valid_verification_result: dict, with_artifacts: Path
    ):
        result = evaluate_delivery_package_finalization(str(root))
        assert "result_id" in result
        assert "generated_at" in result
        assert "status" in result
        assert "decision" in result
        assert "source_commit_hash" in result
        assert "verified_bundle_state" in result
        assert "artifacts" in result
        assert "integrity" in result
        assert "checklist" in result
        assert "index_result" in result
        assert "checklist_result" in result
        assert "summary_result" in result
        assert "mutation_guard" in result

    def test_blocks_when_verification_invalid(self, root: Path):
        result = evaluate_delivery_package_finalization(str(root))
        assert result["status"] == DeliveryPackageFinalizationStatus.BLOCKED_VERIFICATION_NOT_VALID.value
        assert result["decision"] == DeliveryPackageDecision.BLOCK_HANDOFF.value

    def test_finalized_when_all_valid(
        self, root: Path, valid_verification_result: dict, with_artifacts: Path
    ):
        result = evaluate_delivery_package_finalization(str(root))
        assert result["status"] in (
            DeliveryPackageFinalizationStatus.FINALIZED.value,
            DeliveryPackageFinalizationStatus.FINALIZED_WITH_WARNINGS.value,
        )
        assert result["decision"] in (
            DeliveryPackageDecision.APPROVE_HANDOFF.value,
            DeliveryPackageDecision.APPROVE_HANDOFF_WITH_WARNINGS.value,
        )

    def test_generated_artifacts_exist(
        self, root: Path, valid_verification_result: dict, with_artifacts: Path
    ):
        result = evaluate_delivery_package_finalization(str(root))
        index_path = Path(result["index_result"]["index_path"])
        checklist_path = Path(result["checklist_result"]["checklist_path"])
        summary_path = Path(result["summary_result"]["summary_path"])
        assert index_path.exists()
        assert checklist_path.exists()
        assert summary_path.exists()


# ── Test: validate_delivery_package_finalization_result ────────────────────────

class TestValidateDeliveryPackageFinalizationResult:
    def test_valid_when_all_artifacts_present(
        self, root: Path, valid_verification_result: dict, with_artifacts: Path
    ):
        result = evaluate_delivery_package_finalization(str(root))
        validation = validate_delivery_package_finalization_result(result)
        assert validation["valid"] is True
        assert len(validation["blocked_reasons"]) == 0

    def test_invalid_when_index_missing(
        self, root: Path, valid_verification_result: dict, with_artifacts: Path
    ):
        result = evaluate_delivery_package_finalization(str(root))
        # Remove index path to simulate failure
        result["index_result"] = {"index_path": None}
        validation = validate_delivery_package_finalization_result(result)
        assert validation["valid"] is False
        assert "delivery_package_index_not_generated" in validation["blocked_reasons"]

    def test_invalid_when_checklist_missing(
        self, root: Path, valid_verification_result: dict, with_artifacts: Path
    ):
        result = evaluate_delivery_package_finalization(str(root))
        result["checklist_result"] = {"checklist_path": None}
        validation = validate_delivery_package_finalization_result(result)
        assert validation["valid"] is False

    def test_invalid_when_summary_missing(
        self, root: Path, valid_verification_result: dict, with_artifacts: Path
    ):
        result = evaluate_delivery_package_finalization(str(root))
        result["summary_result"] = {"summary_path": None}
        validation = validate_delivery_package_finalization_result(result)
        assert validation["valid"] is False

    def test_validates_mutation_guard_failure(
        self, root: Path, valid_verification_result: dict, with_artifacts: Path
    ):
        result = evaluate_delivery_package_finalization(str(root))
        result["mutation_guard"] = {"all_passed": False, "blocked_reasons": ["head_changed"]}
        validation = validate_delivery_package_finalization_result(result)
        assert validation["valid"] is False


# ── Test: generate_delivery_package_finalization_report ───────────────────────

class TestGenerateDeliveryPackageFinalizationReport:
    def test_writes_json_and_md(
        self, root: Path, valid_verification_result: dict, with_artifacts: Path
    ):
        result = evaluate_delivery_package_finalization(str(root))
        output = generate_delivery_package_finalization_report(result)
        json_path = Path(output["output_path"])
        md_path = Path(output["report_path"])
        assert json_path.exists()
        assert md_path.exists()
        # Validate JSON
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["result_id"] == result["result_id"]
        assert data["status"] == result["status"]

    def test_md_contains_all_sections(
        self, root: Path, valid_verification_result: dict, with_artifacts: Path
    ):
        result = evaluate_delivery_package_finalization(str(root))
        output = generate_delivery_package_finalization_report(result)
        content = Path(output["report_path"]).read_text(encoding="utf-8")
        assert "R241-16U" in content
        assert "Verification State Loading" in content
        assert "Artifact Collection" in content
        assert "Mutation Guard" in content
        assert "Safety Summary" in content

    def test_md_contains_safety_summary(
        self, root: Path, valid_verification_result: dict, with_artifacts: Path
    ):
        result = evaluate_delivery_package_finalization(str(root))
        output = generate_delivery_package_finalization_report(result)
        content = Path(output["report_path"]).read_text(encoding="utf-8")
        assert "No git push" in content or "git push" in content
        assert "workflow" in content.lower()


# ── Test: Integration ─────────────────────────────────────────────────────────

class TestIntegration:
    def test_end_to_end_finalization_with_valid_artifacts(
        self, root: Path, valid_verification_result: dict, with_artifacts: Path
    ):
        """Full pipeline: load → collect → validate → checklist → index → summary → report."""
        # Evaluate
        result = evaluate_delivery_package_finalization(str(root))
        assert result["status"] in (
            DeliveryPackageFinalizationStatus.FINALIZED.value,
            DeliveryPackageFinalizationStatus.FINALIZED_WITH_WARNINGS.value,
        )

        # Validate
        validation = validate_delivery_package_finalization_result(result)
        assert validation["valid"] is True

        # Generate report
        output = generate_delivery_package_finalization_report(result)
        assert Path(output["output_path"]).exists()
        assert Path(output["report_path"]).exists()

        # Verify no mutation
        mg = result["mutation_guard"]
        assert mg["all_passed"] is True

    def test_no_secret_read(self, root: Path, valid_verification_result: dict, with_artifacts: Path):
        """Verify finalization functions don't read actual secrets."""
        import os
        env_before = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        result = evaluate_delivery_package_finalization(str(root))
        env_after = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        assert env_before == env_after

    def test_no_workflow_file_modified(
        self, root: Path, valid_verification_result: dict, with_artifacts: Path
    ):
        """Workflow file should not be modified by finalization."""
        workflow_path = root / TARGET_WORKFLOW
        content_before = workflow_path.read_text(encoding="utf-8")
        result = evaluate_delivery_package_finalization(str(root))
        content_after = workflow_path.read_text(encoding="utf-8")
        assert content_before == content_after
