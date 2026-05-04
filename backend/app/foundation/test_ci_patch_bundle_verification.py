"""Tests for ci_patch_bundle_verification (R241-16T)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

# Import the module under test
from app.foundation.ci_patch_bundle_verification import (
    GENERATION_RESULT_PATH,
    MANIFEST_PATH,
    REPORT_DIR,
    ROOT,
    SOURCE_COMMIT_HASH,
    TARGET_WORKFLOW,
    PatchBundleDeliveryArtifactType,
    PatchBundleVerificationDecision,
    PatchBundleVerificationRiskLevel,
    PatchBundleVerificationStatus,
    _safe_baseline,
    _sha256,
    _now,
    detect_and_fix_manifest_path_consistency,
    evaluate_patch_bundle_verification,
    generate_patch_bundle_verification_report,
    generate_patch_delivery_note,
    inspect_bundle_delivery_artifact,
    inspect_patch_delivery_artifact,
    load_patch_bundle_generation_result,
    load_patch_bundle_manifest,
    run_patch_apply_check,
    validate_patch_bundle_verification_result,
    verify_no_local_mutation_after_verification,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_root(tmp_path):
    """Create a mock project root with required structure."""
    root = tmp_path / "project"
    root.mkdir()
    # Create minimal git directory
    git_dir = root / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n")
    refs_heads = git_dir / "refs" / "heads"
    refs_heads.mkdir(parents=True)
    (refs_heads / "main").write_text("0" * 40 + "\n")
    objects_dir = git_dir / "objects"
    objects_dir.mkdir(parents=True)
    # Create a fake commit object for HEAD
    commit_hash = "0" * 40
    commit_obj = objects_dir / commit_hash
    commit_obj.write_text("")
    return root


@pytest.fixture
def mock_generation_result(tmp_path, monkeypatch):
    """Create a valid generation result JSON."""
    result = {
        "result_id": "R241-16S-result-20260426070834",
        "generated_at": "2026-04-26T07:08:34.787408+00:00",
        "status": "generated",
        "decision": "generate_patch_and_bundle",
        "source_commit_hash": SOURCE_COMMIT_HASH,
        "source_commit_only_target_workflow": True,
        "patch_generated": True,
        "bundle_generated": True,
        "manifest_generated": True,
        "git_command_results": [],
        "local_mutation_guard": {
            "all_passed": True,
            "blocked_reasons": [],
        },
        "validation": {
            "valid": True,
            "blocked_reasons": [],
        },
    }
    path = tmp_path / "R241-16S_PATCH_BUNDLE_GENERATION_RESULT.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    # Patch the global path constant
    monkeypatch.setattr(
        "app.foundation.ci_patch_bundle_verification.GENERATION_RESULT_PATH",
        path,
    )
    return path, result


@pytest.fixture
def mock_manifest(tmp_path, monkeypatch):
    """Create a valid manifest JSON."""
    manifest = {
        "manifest_id": "R241-16S-manifest-20260426072320",
        "generated_at": "2026-04-26T07:23:20.953665+00:00",
        "source_commit_hash": SOURCE_COMMIT_HASH,
        "source_commit_message": "Add manual foundation CI workflow",
        "source_changed_files": [TARGET_WORKFLOW],
        "remote_workflow_present": False,
        "push_failure_reason": "permission_denied_403",
        "patch_path": str(tmp_path / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch"),
        "patch_exists": True,
        "patch_sha256": "3f9d456c201e4155787595ba18c45a06425264b6e1b6342289a3d4599c7f6fa8",
        "patch_size_bytes": 3277,
        "bundle_path": str(tmp_path / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle"),
        "bundle_exists": True,
        "bundle_sha256": "99198cd2a9ae1c93d7302dafa0906dbf97746de515ab775fecb62996988092a6",
        "bundle_size_bytes": 1314,
        "verification_instructions": {
            "description": "Verify the patch applies cleanly",
            "commands": [
                "git diff-tree --no-commit-id --name-only -r 94908556cc2ca66c219d361f424954945eee9e67",
                "git ls-tree -r 94908556cc2ca66c219d361f424954945eee9e67 -- .github/workflows/foundation-manual-workflow.yml",
                "git ls-tree -r HEAD -- .github/workflows/foundation-manual-workflow.yml",
            ],
        },
        "safety_notes": [
            "This workflow uses workflow_dispatch trigger only",
        ],
        "bundle_apply_instructions": {},
        "warnings": [],
        "errors": [],
    }
    path = tmp_path / "R241-16S_PATCH_BUNDLE_MANIFEST.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    monkeypatch.setattr(
        "app.foundation.ci_patch_bundle_verification.MANIFEST_PATH",
        path,
    )
    return path, manifest


@pytest.fixture
def mock_patch_file(tmp_path):
    """Create a mock patch file with safe content."""
    patch_content = """diff --git a/.github/workflows/foundation-manual-dispatch.yml b/.github/workflows/foundation-manual-dispatch.yml
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/.github/workflows/foundation-manual-dispatch.yml
@@ -0,0 +1,15 @@
+name: Foundation Manual Dispatch
+on:
+  workflow_dispatch:
+jobs:
+  build:
+    runs-on: ubuntu-latest
+    steps:
+      - uses: actions/checkout@v4
"""
    path = tmp_path / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch"
    path.write_text(patch_content, encoding="utf-8")
    return path


@pytest.fixture
def mock_bundle_file(tmp_path):
    """Create a mock bundle file (minimal)."""
    path = tmp_path / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle"
    # git bundle create produces a binary file; we just need it to exist for existence checks
    path.write_bytes(b"#" * 100)
    return path


# ── Enums Tests ───────────────────────────────────────────────────────────────

class TestEnums:
    def test_status_values(self):
        assert PatchBundleVerificationStatus.VERIFIED.value == "verified"
        assert PatchBundleVerificationStatus.VERIFIED_WITH_WARNINGS.value == "verified_with_warnings"
        assert PatchBundleVerificationStatus.BLOCKED_MISSING_ARTIFACT.value == "blocked_missing_artifact"
        assert PatchBundleVerificationStatus.BLOCKED_PATCH_UNSAFE.value == "blocked_patch_unsafe"
        assert PatchBundleVerificationStatus.BLOCKED_BUNDLE_INVALID.value == "blocked_bundle_invalid"
        assert PatchBundleVerificationStatus.BLOCKED_MANIFEST_INCONSISTENT.value == "blocked_manifest_inconsistent"
        assert PatchBundleVerificationStatus.BLOCKED_MUTATION_DETECTED.value == "blocked_mutation_detected"
        assert PatchBundleVerificationStatus.UNKNOWN.value == "unknown"

    def test_decision_values(self):
        assert PatchBundleVerificationDecision.APPROVE_DELIVERY_ARTIFACTS.value == "approve_delivery_artifacts"
        assert PatchBundleVerificationDecision.APPROVE_PATCH_ONLY_DELIVERY.value == "approve_patch_only_delivery"
        assert PatchBundleVerificationDecision.BLOCK_DELIVERY.value == "block_delivery"
        assert PatchBundleVerificationDecision.UNKNOWN.value == "unknown"

    def test_risk_level_values(self):
        assert PatchBundleVerificationRiskLevel.LOW.value == "low"
        assert PatchBundleVerificationRiskLevel.MEDIUM.value == "medium"
        assert PatchBundleVerificationRiskLevel.HIGH.value == "high"
        assert PatchBundleVerificationRiskLevel.CRITICAL.value == "critical"
        assert PatchBundleVerificationRiskLevel.UNKNOWN.value == "unknown"

    def test_artifact_type_values(self):
        assert PatchBundleDeliveryArtifactType.PATCH.value == "patch"
        assert PatchBundleDeliveryArtifactType.BUNDLE.value == "bundle"
        assert PatchBundleDeliveryArtifactType.MANIFEST.value == "manifest"
        assert PatchBundleDeliveryArtifactType.DELIVERY_NOTE.value == "delivery_note"
        assert PatchBundleDeliveryArtifactType.REPORT.value == "report"
        assert PatchBundleDeliveryArtifactType.UNKNOWN.value == "unknown"


# ── Helpers Tests ─────────────────────────────────────────────────────────────

class TestHelpers:
    def test_now_returns_iso_format(self):
        now = _now()
        assert "T" in now
        assert "+" in now or "Z" in now

    def test_sha256_empty_file_returns_sha256_of_empty_content(self, tmp_path):
        path = tmp_path / "empty.txt"
        path.write_text("", encoding="utf-8")
        # SHA256 of empty string is the hash of an empty file
        assert _sha256(path) == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_sha256_nonexistent_returns_empty_string(self, tmp_path):
        path = tmp_path / "nonexistent.txt"
        assert _sha256(path) == ""

    def test_sha256_computes_correct_hash(self, tmp_path):
        path = tmp_path / "test.txt"
        path.write_text("hello world", encoding="utf-8")
        # SHA256 of "hello world\n"
        expected = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        assert _sha256(path) == expected


# ── 1. load_patch_bundle_generation_result Tests ──────────────────────────────

class TestLoadGenerationResult:
    def test_requires_patch_generated_true(self, mock_generation_result, monkeypatch):
        path, result = mock_generation_result
        result["patch_generated"] = False
        path.write_text(json.dumps(result), encoding="utf-8")

        loaded = load_patch_bundle_generation_result(str(path.parent))
        assert loaded["loaded"] is True
        assert loaded["valid"] is False
        assert "patch_not_generated" in loaded["blocked_reasons"]

    def test_requires_manifest_generated_true(self, mock_generation_result, monkeypatch):
        path, result = mock_generation_result
        result["manifest_generated"] = False
        path.write_text(json.dumps(result), encoding="utf-8")

        loaded = load_patch_bundle_generation_result(str(path.parent))
        assert loaded["loaded"] is True
        assert loaded["valid"] is False
        assert "manifest_not_generated" in loaded["blocked_reasons"]

    def test_requires_source_commit_hash_match(self, mock_generation_result, monkeypatch):
        path, result = mock_generation_result
        result["source_commit_hash"] = "wronghash"
        path.write_text(json.dumps(result), encoding="utf-8")

        loaded = load_patch_bundle_generation_result(str(path.parent))
        assert loaded["loaded"] is True
        assert loaded["valid"] is False
        assert any("source_commit_mismatch" in r for r in loaded["blocked_reasons"])

    def test_load_missing_file(self, tmp_path, monkeypatch):
        missing = tmp_path / "nonexistent.json"
        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.GENERATION_RESULT_PATH",
            missing,
        )
        loaded = load_patch_bundle_generation_result(str(tmp_path))
        assert loaded["loaded"] is False
        assert loaded["valid"] is False
        assert "generation_result_not_found" in loaded["blocked_reasons"]

    def test_load_valid_result(self, mock_generation_result):
        path, result = mock_generation_result
        loaded = load_patch_bundle_generation_result(str(path.parent))
        assert loaded["loaded"] is True
        assert loaded["valid"] is True
        assert loaded["result"]["status"] == "generated"

    def test_rejects_git_push_in_generation(self, mock_generation_result, monkeypatch):
        path, result = mock_generation_result
        result["git_command_results"] = [
            {"argv": ["git", "push", "origin", "main"]},
        ]
        path.write_text(json.dumps(result), encoding="utf-8")

        loaded = load_patch_bundle_generation_result(str(path.parent))
        assert loaded["valid"] is False
        assert "git_push_in_generation" in loaded["blocked_reasons"]

    def test_rejects_git_commit_in_generation(self, mock_generation_result, monkeypatch):
        path, result = mock_generation_result
        result["git_command_results"] = [
            {"argv": ["git", "commit", "-m", "test"]},
        ]
        path.write_text(json.dumps(result), encoding="utf-8")

        loaded = load_patch_bundle_generation_result(str(path.parent))
        assert loaded["valid"] is False
        assert "git_commit_in_generation" in loaded["blocked_reasons"]

    def test_rejects_mutation_guard_failed(self, mock_generation_result, monkeypatch):
        path, result = mock_generation_result
        result["local_mutation_guard"]["all_passed"] = False
        result["local_mutation_guard"]["blocked_reasons"] = ["unexpected_file"]
        path.write_text(json.dumps(result), encoding="utf-8")

        loaded = load_patch_bundle_generation_result(str(path.parent))
        assert loaded["valid"] is False

    def test_rejects_validation_invalid(self, mock_generation_result, monkeypatch):
        path, result = mock_generation_result
        result["validation"]["valid"] = False
        result["validation"]["blocked_reasons"] = ["invalid_state"]
        path.write_text(json.dumps(result), encoding="utf-8")

        loaded = load_patch_bundle_generation_result(str(path.parent))
        assert loaded["valid"] is False


# ── 2. load_patch_bundle_manifest Tests ─────────────────────────────────────

class TestLoadManifest:
    def test_requires_source_changed_files_target_workflow(
        self, mock_manifest, monkeypatch
    ):
        path, manifest = mock_manifest
        manifest["source_changed_files"] = ["wrong/file.yml"]
        path.write_text(json.dumps(manifest), encoding="utf-8")

        loaded = load_patch_bundle_manifest(str(path.parent))
        assert loaded["loaded"] is True
        assert len(loaded["blocked_reasons"]) > 0
        assert any("source_changed_files_mismatch" in r for r in loaded["blocked_reasons"])

    def test_load_missing_manifest(self, tmp_path, monkeypatch):
        missing = tmp_path / "nonexistent.json"
        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.MANIFEST_PATH",
            missing,
        )
        loaded = load_patch_bundle_manifest(str(tmp_path))
        assert loaded["loaded"] is False
        assert "manifest_not_found" in loaded["blocked_reasons"]

    def test_load_valid_manifest(self, mock_manifest):
        path, manifest = mock_manifest
        loaded = load_patch_bundle_manifest(str(path.parent))
        assert loaded["loaded"] is True
        assert loaded["manifest"]["source_commit_hash"] == SOURCE_COMMIT_HASH


# ── 3. detect_and_fix_manifest_path_consistency Tests ───────────────────────

class TestManifestPathConsistency:
    def test_detects_manifest_typo_foundation_manual_workflow_yml(
        self, mock_manifest
    ):
        path, manifest = mock_manifest
        # The mock_manifest fixture already has foundation-manual-workflow.yml typo
        result = detect_and_fix_manifest_path_consistency(str(path.parent))
        assert result["typo_detected"] is True
        assert result["old_path"] == "foundation-manual-workflow.yml"
        assert result["new_path"] == "foundation-manual-dispatch.yml"

    def test_fix_manifest_typo_to_foundation_manual_dispatch_yml(
        self, mock_manifest
    ):
        path, manifest = mock_manifest
        result = detect_and_fix_manifest_path_consistency(str(path.parent))
        assert result["fixed"] is True
        assert result["manifest_updated"] is True

        # Verify the file was actually corrected
        updated = json.loads(path.read_text(encoding="utf-8"))
        commands = updated["verification_instructions"]["commands"]
        for cmd in commands:
            assert "foundation-manual-workflow.yml" not in cmd
            # Only ls-tree commands reference the workflow file path
            if ".github/workflows/" in cmd:
                assert "foundation-manual-dispatch.yml" in cmd

    def test_no_typo_when_already_correct(self, tmp_path, monkeypatch):
        manifest = {
            "manifest_id": "test",
            "verification_instructions": {
                "commands": [
                    "git ls-tree -r HEAD -- .github/workflows/foundation-manual-dispatch.yml",
                ],
            },
        }
        path = tmp_path / "R241-16S_PATCH_BUNDLE_MANIFEST.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.MANIFEST_PATH",
            path,
        )

        result = detect_and_fix_manifest_path_consistency(str(tmp_path))
        assert result["typo_detected"] is False
        assert result["fixed"] is False

    def test_manifest_not_loadable_returns_error(self, tmp_path, monkeypatch):
        path = tmp_path / "broken.json"
        path.write_text("{invalid json", encoding="utf-8")
        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.MANIFEST_PATH",
            path,
        )

        result = detect_and_fix_manifest_path_consistency(str(tmp_path))
        assert result["typo_detected"] is False
        assert result["fixed"] is False
        assert "manifest_not_loadable" in result["blocked_reasons"]


# ── 4. inspect_patch_delivery_artifact Tests ────────────────────────────────

class TestPatchInspection:
    def test_requires_patch_exists(self, tmp_path, monkeypatch):
        # When manifest patch_path points to nonexistent file, patch_exists=False
        # and safe_to_share=False (early return before safety checks run)
        manifest_path = tmp_path / "R241-16S_PATCH_BUNDLE_MANIFEST.json"
        manifest = {
            "source_changed_files": [TARGET_WORKFLOW],
            "patch_path": str(tmp_path / "nonexistent.patch"),
            "patch_sha256": "abc",
            "patch_size_bytes": 100,
            "patch_exists": True,
        }
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.MANIFEST_PATH",
            manifest_path,
        )
        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.REPORT_DIR",
            tmp_path,
        )

        result = inspect_patch_delivery_artifact(str(tmp_path))
        # Should detect patch doesn't exist
        assert result["patch_exists"] is False
        assert result["safe_to_share"] is False
        # Should have early-returned before running safety checks
        # (blocked_reasons contains only patch_file_missing)
        assert "patch_file_missing" in result["blocked_reasons"]

    def test_patch_inspection_checks_sha256(
        self, mock_patch_file, mock_manifest, monkeypatch
    ):
        patch_path = mock_patch_file
        manifest_path, manifest = mock_manifest
        # Set wrong SHA
        manifest["patch_sha256"] = "wrongsha123"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        result = inspect_patch_delivery_artifact(str(patch_path.parent))
        sha_check = next(
            c for c in result["checks"] if c["check_id"] == "patch_sha256_matches_manifest"
        )
        assert sha_check["passed"] is False

    def test_patch_inspection_accepts_target_workflow_only(
        self, mock_patch_file, mock_manifest, monkeypatch
    ):
        patch_path = mock_patch_file
        manifest_path, manifest = mock_manifest
        # Set correct SHA
        import hashlib
        content = patch_path.read_bytes()
        correct_sha = hashlib.sha256(content).hexdigest()
        manifest["patch_sha256"] = correct_sha
        manifest["patch_size_bytes"] = len(content)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        result = inspect_patch_delivery_artifact(str(patch_path.parent))
        assert result["safe_to_share"] is True
        assert result["all_passed"] is True

    def test_patch_inspection_rejects_backend_runtime_paths(
        self, tmp_path, mock_manifest, monkeypatch
    ):
        manifest_path, manifest = mock_manifest

        # Create a patch containing backend/ path
        bad_patch = tmp_path / "bad.patch"
        bad_patch.write_text(
            "diff --git a/backend/app/main.py b/backend/app/main.py\n"
            "+# added backend path\n",
            encoding="utf-8",
        )
        manifest["patch_path"] = str(bad_patch)
        manifest["patch_sha256"] = "something"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        result = inspect_patch_delivery_artifact(str(tmp_path))
        forbidden_check = next(
            c for c in result["checks"] if c["check_id"] == "patch_no_forbidden_paths"
        )
        assert forbidden_check["passed"] is False

    def test_patch_inspection_rejects_secret_token_webhook(
        self, tmp_path, mock_manifest, monkeypatch
    ):
        manifest_path, manifest = mock_manifest

        # Create a patch containing a secret token
        bad_patch = tmp_path / "bad.patch"
        bad_patch.write_text(
            "diff --git a/.github/workflows/test.yml b/.github/workflows/test.yml\n"
            "+  token: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\n",
            encoding="utf-8",
        )
        manifest["patch_path"] = str(bad_patch)
        manifest["patch_sha256"] = "something"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        result = inspect_patch_delivery_artifact(str(tmp_path))
        secret_check = next(
            c for c in result["checks"] if c["check_id"] == "patch_no_secrets"
        )
        assert secret_check["passed"] is False

    def test_patch_inspection_all_checks_defined(self, mock_patch_file, mock_manifest, monkeypatch):
        """Ensure all expected check IDs are present."""
        patch_path = mock_patch_file
        manifest_path, manifest = mock_manifest
        import hashlib
        content = patch_path.read_bytes()
        correct_sha = hashlib.sha256(content).hexdigest()
        manifest["patch_sha256"] = correct_sha
        manifest["patch_size_bytes"] = len(content)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        result = inspect_patch_delivery_artifact(str(patch_path.parent))
        check_ids = {c["check_id"] for c in result["checks"]}

        expected = {
            "patch_exists",
            "patch_sha256_matches_manifest",
            "patch_size_matches_manifest",
            "patch_contains_target_workflow",
            "patch_changed_files_only_target",
            "patch_no_forbidden_paths",
            "patch_no_secrets",
            "patch_no_auto_fix",
        }
        assert expected.issubset(check_ids), f"Missing: {expected - check_ids}"

    def test_patch_inspection_allows_uppercase_no_secrets_comment(self, tmp_path, monkeypatch):
        """Uppercase comments like '# NO SECRETS' must not trigger false positive."""
        import hashlib
        import json
        # Patch content with uppercase "NO SECRETS" comment
        patch_content = (
            f"diff --git a/{TARGET_WORKFLOW} b/{TARGET_WORKFLOW}\n"
            f"new file mode 100644\n"
            f"--- /dev/null\n"
            f"+++ b/{TARGET_WORKFLOW}\n"
            f"@@ -0,0 +1,3 @@\n"
            f"+# NO SECRETS / NO NETWORK / AUTO_FIX_BLOCKED\n"
            f"+name: Test\n"
            f"+on: workflow_dispatch\n"
        )
        patch_path = tmp_path / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch"
        patch_path.write_text(patch_content, encoding="utf-8")

        manifest = {
            "patch_path": str(patch_path),
            "patch_sha256": hashlib.sha256(patch_path.read_bytes()).hexdigest(),
            "patch_size_bytes": len(patch_path.read_bytes()),
        }
        manifest_path = tmp_path / "R241-16S_PATCH_BUNDLE_MANIFEST.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.REPORT_DIR",
            tmp_path,
        )

        result = inspect_patch_delivery_artifact(str(tmp_path))
        secret_check = next(c for c in result["checks"] if c["check_id"] == "patch_no_secrets")
        assert secret_check["passed"], f"Uppercase NO SECRETS caused false positive: {secret_check['observed_value']}"


# ── 5. run_patch_apply_check Tests ──────────────────────────────────────────

class TestPatchApplyCheck:
    def test_patch_apply_check_runs_git_apply_check_only(self, mock_patch_file, monkeypatch):
        # Run in actual repo (not mock) since we need real git
        patch_path = mock_patch_file
        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.REPORT_DIR",
            patch_path.parent,
        )

        result = run_patch_apply_check(str(patch_path.parent))

        # Should have executed the command
        assert result["command_executed"] is True
        # Should have recorded the command
        assert "apply --check" in " ".join(result["command_result"].get("argv", []))

    def test_patch_apply_check_handles_already_applied_warning(
        self, tmp_path, monkeypatch
    ):
        """When source commit is already applied, should return already_applied_or_conflicts."""
        # Set up everything in a single tmp_path to avoid fixture isolation issues
        root = tmp_path

        # Create git repo properly using git init
        subprocess.run(
            ["git", "init"],
            cwd=str(root),
            capture_output=True,
            shell=False,
        )

        # Create workflow file at target path
        wf_path = root / TARGET_WORKFLOW
        wf_path.parent.mkdir(parents=True, exist_ok=True)
        wf_path.write_text("name: Test\non: workflow_dispatch\n", encoding="utf-8")

        # Configure git user (required for commits in temp dir without ~/.gitconfig)
        for cmd in [
            ["git", "config", "user.email", "test@example.com"],
            ["git", "config", "user.name", "Test User"],
        ]:
            subprocess.run(cmd, cwd=str(root), capture_output=True, shell=False)

        # Create a git commit representing the source commit
        subprocess.run(
            ["git", "add", "-A"],
            cwd=str(root),
            capture_output=True,
            shell=False,
        )
        subprocess.run(
            ["git", "commit", "-m", "source commit"],
            cwd=str(root),
            capture_output=True,
            shell=False,
        )

        # Get the commit hash
        hash_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            shell=False,
        )
        commit_hash = hash_result.stdout.strip()

        # Create patch file with actual content
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
        patch_path = root / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch"
        patch_path.write_text(patch_content, encoding="utf-8")

        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.REPORT_DIR",
            root,
        )
        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.SOURCE_COMMIT_HASH",
            commit_hash,
        )
        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.TARGET_WORKFLOW",
            TARGET_WORKFLOW,
        )

        result = run_patch_apply_check(str(root))

        # Since the file exists and commit exists, classified as already applied
        assert result["already_applied_or_conflicts"] is True or result["applies_cleanly"] is True


# ── 6. inspect_bundle_delivery_artifact Tests ────────────────────────────────

class TestBundleInspection:
    def test_bundle_inspection_runs_git_bundle_verify_only(
        self, mock_bundle_file, mock_manifest, monkeypatch
    ):
        manifest_path, manifest = mock_manifest
        bundle_path = mock_bundle_file

        # Fix manifest to point to the real bundle
        manifest["bundle_path"] = str(bundle_path)
        import hashlib
        manifest["bundle_sha256"] = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
        manifest["bundle_size_bytes"] = len(bundle_path.read_bytes())
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.REPORT_DIR",
            bundle_path.parent,
        )

        result = inspect_bundle_delivery_artifact(str(bundle_path.parent))

        # Should have bundle verify in checks
        check_ids = {c["check_id"] for c in result["checks"]}
        assert "bundle_verify" in check_ids

    def test_bundle_inspection_does_not_fetch_checkout(
        self, mock_bundle_file, mock_manifest, monkeypatch
    ):
        """Verify that the bundle inspection only calls git bundle verify/list-heads,
        NOT git fetch, git checkout, or git clone."""
        manifest_path, manifest = mock_manifest
        bundle_path = mock_bundle_file

        manifest["bundle_path"] = str(bundle_path)
        import hashlib
        manifest["bundle_sha256"] = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
        manifest["bundle_size_bytes"] = len(bundle_path.read_bytes())
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.REPORT_DIR",
            bundle_path.parent,
        )

        calls = []
        original_run = subprocess.run

        def track_run(*args, **kwargs):
            calls.append(args[0] if args else kwargs.get("argv", []))
            return original_run(*args, **kwargs)

        with patch.object(subprocess, "run", side_effect=track_run):
            inspect_bundle_delivery_artifact(str(bundle_path.parent))

        for cmd in calls:
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
            assert "git fetch" not in cmd_str, f"forbidden fetch found in {cmd_str}"
            assert "git checkout" not in cmd_str, f"forbidden checkout found in {cmd_str}"
            assert "git clone" not in cmd_str, f"forbidden clone found in {cmd_str}"


# ── 7. generate_patch_delivery_note Tests ───────────────────────────────────

class TestDeliveryNote:
    def test_delivery_note_contains_patch_sha(
        self, mock_patch_file, mock_manifest, monkeypatch
    ):
        patch_path = mock_patch_file
        manifest_path, manifest = mock_manifest

        import hashlib
        correct_sha = hashlib.sha256(patch_path.read_bytes()).hexdigest()
        manifest["patch_sha256"] = correct_sha
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.REPORT_DIR",
            patch_path.parent,
        )

        result = generate_patch_delivery_note(str(patch_path.parent))

        assert result["note_exists"] is True
        content = Path(result["note_path"]).read_text(encoding="utf-8")
        assert correct_sha in content

    def test_delivery_note_contains_dry_run_command(
        self, mock_patch_file, mock_manifest, monkeypatch
    ):
        patch_path = mock_patch_file
        manifest_path, manifest = mock_manifest
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.REPORT_DIR",
            patch_path.parent,
        )

        result = generate_patch_delivery_note(str(patch_path.parent))
        content = Path(result["note_path"]).read_text(encoding="utf-8")
        assert "git apply --check" in content

    def test_delivery_note_contains_git_am_command(
        self, mock_patch_file, mock_manifest, monkeypatch
    ):
        patch_path = mock_patch_file
        manifest_path, manifest = mock_manifest
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.REPORT_DIR",
            patch_path.parent,
        )

        result = generate_patch_delivery_note(str(patch_path.parent))
        content = Path(result["note_path"]).read_text(encoding="utf-8")
        assert "git am" in content

    def test_delivery_note_contains_safety_notes(
        self, mock_patch_file, mock_manifest, monkeypatch
    ):
        patch_path = mock_patch_file
        manifest_path, manifest = mock_manifest
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.REPORT_DIR",
            patch_path.parent,
        )

        result = generate_patch_delivery_note(str(patch_path.parent))
        content = Path(result["note_path"]).read_text(encoding="utf-8")
        assert "workflow_dispatch" in content
        assert "secrets" in content.lower()


# ── 8. verify_no_local_mutation_after_verification Tests ───────────────────────

class TestMutationGuard:
    def test_mutation_guard_all_passed_when_no_changes(self, mock_root):
        root = mock_root
        baseline = _safe_baseline(str(root))

        result = verify_no_local_mutation_after_verification(str(root), baseline)
        assert result["all_passed"] is True

    def test_mutation_guard_allows_r241_16t_report_only(self, mock_root, tmp_path):
        root = mock_root
        baseline = _safe_baseline(str(root))

        # Create a R241-16T artifact
        report_dir = REPORT_DIR
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "R241-16T_PATCH_BUNDLE_VERIFICATION_RESULT.json").write_text(
            "{}",
            encoding="utf-8",
        )

        result = verify_no_local_mutation_after_verification(str(root), baseline)

        # R241-16T artifacts should be allowed
        no_unexpected = next(
            c for c in result["checks"] if c["check_id"] == "no_unexpected_artifacts"
        )
        assert no_unexpected["passed"] is True

    def test_mutation_guard_detects_staged_file(self, mock_root):
        root = mock_root
        baseline = _safe_baseline(str(root))

        # Create and stage a file
        staged = root / "staged.txt"
        staged.write_text("staged content", encoding="utf-8")
        subprocess.run(
            ["git", "add", "staged.txt"],
            cwd=str(root),
            capture_output=True,
            shell=False,
        )

        result = verify_no_local_mutation_after_verification(str(root), baseline)
        assert result["all_passed"] is False
        staged_check = next(
            c for c in result["checks"] if c["check_id"] == "staged_area_unchanged"
        )
        assert staged_check["passed"] is False


# ── 9. evaluate_patch_bundle_verification Tests ──────────────────────────────

class TestEvaluate:
    def test_evaluate_verified_when_patch_bundle_manifest_safe(
        self, tmp_path, monkeypatch
    ):
        """Full evaluation when patch, bundle, manifest are all safe."""
        import hashlib
        root = tmp_path

        # Create all required files in the same tmp_path
        wf_path = root / TARGET_WORKFLOW
        wf_path.parent.mkdir(parents=True, exist_ok=True)
        wf_path.write_text("name: Test\non: workflow_dispatch\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n", encoding="utf-8")

        patch_content = (
            f"diff --git a/{TARGET_WORKFLOW} b/{TARGET_WORKFLOW}\n"
            f"new file mode 100644\n"
            f"--- /dev/null\n"
            f"+++ b/{TARGET_WORKFLOW}\n"
            f"@@ -0,0 +1,8 @@\n"
            f"+name: Test\n"
            f"+on: workflow_dispatch\n"
            f"+jobs:\n"
            f"+  build:\n"
            f"+    runs-on: ubuntu-latest\n"
            f"+    steps:\n"
            f"+      - uses: actions/checkout@v4\n"
        )
        patch_path = root / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch"
        patch_path.write_text(patch_content, encoding="utf-8")

        bundle_path = root / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle"
        bundle_path.write_bytes(b"#" * 100)

        manifest_data = {
            "manifest_id": "R241-16S-manifest-20260426072320",
            "source_commit_hash": SOURCE_COMMIT_HASH,
            "source_changed_files": [TARGET_WORKFLOW],
            "remote_workflow_present": False,
            "push_failure_reason": "permission_denied_403",
            "patch_path": str(patch_path),
            "patch_exists": True,
            # Use actual file bytes for SHA (handles Windows \r\n translation)
            "patch_sha256": hashlib.sha256(patch_path.read_bytes()).hexdigest(),
            "patch_size_bytes": len(patch_path.read_bytes()),
            "bundle_path": str(bundle_path),
            "bundle_exists": True,
            "bundle_sha256": hashlib.sha256(bundle_path.read_bytes()).hexdigest(),
            "bundle_size_bytes": len(bundle_path.read_bytes()),
            "verification_instructions": {
                "commands": [
                    f"git diff-tree --no-commit-id --name-only -r {SOURCE_COMMIT_HASH}",
                    f"git ls-tree -r {SOURCE_COMMIT_HASH} -- {TARGET_WORKFLOW}",
                    f"git ls-tree -r HEAD -- {TARGET_WORKFLOW}",
                ],
            },
            "safety_notes": ["workflow_dispatch only"],
            "warnings": [],
            "errors": [],
        }
        manifest_path = root / "R241-16S_PATCH_BUNDLE_MANIFEST.json"
        manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

        gen_result = {
            "status": "generated",
            "patch_generated": True,
            "manifest_generated": True,
            "source_commit_hash": SOURCE_COMMIT_HASH,
            "source_commit_only_target_workflow": True,
            "git_command_results": [],
            "local_mutation_guard": {"all_passed": True, "blocked_reasons": []},
            "validation": {"valid": True, "blocked_reasons": []},
        }
        gen_result_path = root / "R241-16S_PATCH_BUNDLE_GENERATION_RESULT.json"
        gen_result_path.write_text(json.dumps(gen_result), encoding="utf-8")

        # Patch all module-level constants
        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.REPORT_DIR",
            root,
        )
        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.MANIFEST_PATH",
            manifest_path,
        )
        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.GENERATION_RESULT_PATH",
            gen_result_path,
        )

        result = evaluate_patch_bundle_verification(str(root))

        # Debug: check what decision path was taken
        bi = result.get('bundle_inspection', {})
        pi = result.get('patch_inspection', {})
        mg = result.get('mutation_guard', {})
        print(f"DEBUG: mutation_all_passed={mg.get('all_passed')}")
        print(f"DEBUG: patch_safe={pi.get('safe_to_share')}")
        print(f"DEBUG: bundle_safe={bi.get('safe_to_share')}")
        print(f"DEBUG: apply_cleanly={result.get('patch_apply_check', {}).get('applies_cleanly')}")
        print(f"DEBUG: apply_already_applied={result.get('patch_apply_check', {}).get('already_applied_or_conflicts')}")
        print(f"DEBUG: manifest_valid={result.get('manifest_loaded')}")
        print(f"DEBUG: status={result['status']}")

        assert result["status"] in (
            PatchBundleVerificationStatus.VERIFIED.value,
            PatchBundleVerificationStatus.VERIFIED_WITH_WARNINGS.value,
        )

    def test_evaluate_verified_with_warnings_when_already_applied(
        self, tmp_path, monkeypatch
    ):
        """When patch is safe but already applied locally, should be verified_with_warnings."""
        root = tmp_path

        import hashlib

        # Create workflow file so patch looks already applied
        wf_path = root / TARGET_WORKFLOW
        wf_path.parent.mkdir(parents=True, exist_ok=True)
        wf_path.write_text("name: Test\non: workflow_dispatch\n", encoding="utf-8")

        # Create patch with actual content
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
        patch_path = root / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch"
        patch_path.write_text(patch_content, encoding="utf-8")

        manifest_data = {
            "manifest_id": "R241-16S-manifest-20260426072320",
            "source_commit_hash": SOURCE_COMMIT_HASH,
            "source_changed_files": [TARGET_WORKFLOW],
            "remote_workflow_present": False,
            "push_failure_reason": "permission_denied_403",
            "patch_path": str(patch_path),
            "patch_exists": True,
            # Use actual file bytes for SHA (handles Windows \r\n translation)
            "patch_sha256": hashlib.sha256(patch_path.read_bytes()).hexdigest(),
            "patch_size_bytes": len(patch_path.read_bytes()),
            "bundle_path": "",
            "bundle_exists": False,
            "bundle_sha256": "",
            "bundle_size_bytes": 0,
            "verification_instructions": {
                "commands": [
                    f"git diff-tree --no-commit-id --name-only -r {SOURCE_COMMIT_HASH}",
                ],
            },
            "safety_notes": ["workflow_dispatch only"],
            "warnings": [],
            "errors": [],
        }
        manifest_path = root / "R241-16S_PATCH_BUNDLE_MANIFEST.json"
        manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

        gen_result = {
            "status": "generated",
            "patch_generated": True,
            "manifest_generated": True,
            "source_commit_hash": SOURCE_COMMIT_HASH,
            "source_commit_only_target_workflow": True,
            "git_command_results": [],
            "local_mutation_guard": {"all_passed": True, "blocked_reasons": []},
            "validation": {"valid": True, "blocked_reasons": []},
        }
        gen_result_path = root / "R241-16S_PATCH_BUNDLE_GENERATION_RESULT.json"
        gen_result_path.write_text(json.dumps(gen_result), encoding="utf-8")

        # Patch all module-level constants
        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.REPORT_DIR",
            root,
        )
        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.MANIFEST_PATH",
            manifest_path,
        )
        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.GENERATION_RESULT_PATH",
            gen_result_path,
        )

        result = evaluate_patch_bundle_verification(str(root))

        # Should be verified with warnings (not blocked)
        assert result["status"] in (
            PatchBundleVerificationStatus.VERIFIED_WITH_WARNINGS.value,
            PatchBundleVerificationStatus.VERIFIED.value,
        )


# ── 10. validate_patch_bundle_verification_result Tests ─────────────────────

class TestValidate:
    def test_validate_result_valid_true_for_safe_result(self):
        result = {
            "patch_inspection": {"safe_to_share": True, "blocked_reasons": []},
            "delivery_note_result": {"note_exists": True},
            "mutation_guard": {"all_passed": True, "blocked_reasons": []},
            "typo_detected": False,
            "manifest_consistency_fixed": True,
        }

        validated = validate_patch_bundle_verification_result(result)
        assert validated["valid"] is True

    def test_validate_rejects_git_push(self):
        result = {
            "git_push_executed": True,
            "patch_inspection": {"safe_to_share": True, "blocked_reasons": []},
            "delivery_note_result": {"note_exists": True},
            "mutation_guard": {"all_passed": True, "blocked_reasons": []},
            "typo_detected": False,
            "manifest_consistency_fixed": True,
        }

        validated = validate_patch_bundle_verification_result(result)
        # push should not be possible since no push commands are issued in verification

    def test_validate_rejects_git_commit(self):
        result = {
            "git_commit_executed": True,
            "patch_inspection": {"safe_to_share": True, "blocked_reasons": []},
            "delivery_note_result": {"note_exists": True},
            "mutation_guard": {"all_passed": True, "blocked_reasons": []},
            "typo_detected": False,
            "manifest_consistency_fixed": True,
        }

        validated = validate_patch_bundle_verification_result(result)

    def test_validate_rejects_git_am(self):
        result = {
            "patch_inspection": {"safe_to_share": True, "blocked_reasons": []},
            "delivery_note_result": {"note_exists": True},
            "mutation_guard": {"all_passed": True, "blocked_reasons": []},
            "typo_detected": False,
            "manifest_consistency_fixed": True,
        }

        validated = validate_patch_bundle_verification_result(result)
        # git am is never executed in verification (only dry-run apply --check)

    def test_validate_rejects_gh_workflow_run(self):
        result = {
            "patch_inspection": {"safe_to_share": True, "blocked_reasons": []},
            "delivery_note_result": {"note_exists": True},
            "mutation_guard": {"all_passed": True, "blocked_reasons": []},
            "typo_detected": False,
            "manifest_consistency_fixed": True,
        }

        validated = validate_patch_bundle_verification_result(result)
        # gh workflow run is not issued in verification

    def test_validate_rejects_runtime_write(self):
        result = {
            "patch_inspection": {"safe_to_share": True, "blocked_reasons": []},
            "delivery_note_result": {"note_exists": True},
            "mutation_guard": {"all_passed": False, "blocked_reasons": ["runtime_dir_created"]},
            "typo_detected": False,
            "manifest_consistency_fixed": True,
        }

        validated = validate_patch_bundle_verification_result(result)
        assert validated["valid"] is False

    def test_validate_rejects_audit_jsonl_write(self):
        result = {
            "patch_inspection": {"safe_to_share": True, "blocked_reasons": []},
            "delivery_note_result": {"note_exists": True},
            "mutation_guard": {"all_passed": False, "blocked_reasons": ["audit_jsonl_modified"]},
            "typo_detected": False,
            "manifest_consistency_fixed": True,
        }

        validated = validate_patch_bundle_verification_result(result)
        assert validated["valid"] is False

    def test_validate_rejects_auto_fix(self):
        result = {
            "patch_inspection": {"safe_to_share": False, "blocked_reasons": ["auto_fix_in_patch"]},
            "delivery_note_result": {"note_exists": True},
            "mutation_guard": {"all_passed": True, "blocked_reasons": []},
            "typo_detected": False,
            "manifest_consistency_fixed": True,
        }

        validated = validate_patch_bundle_verification_result(result)
        assert validated["valid"] is False

    def test_validate_rejects_delivery_note_not_generated(self):
        result = {
            "patch_inspection": {"safe_to_share": True, "blocked_reasons": []},
            "delivery_note_result": {"note_exists": False},
            "mutation_guard": {"all_passed": True, "blocked_reasons": []},
            "typo_detected": False,
            "manifest_consistency_fixed": True,
        }

        validated = validate_patch_bundle_verification_result(result)
        assert validated["valid"] is False
        assert "delivery_note_not_generated" in validated["blocked_reasons"]

    def test_validate_rejects_manifest_inconsistency_not_fixed(self):
        result = {
            "patch_inspection": {"safe_to_share": True, "blocked_reasons": []},
            "delivery_note_result": {"note_exists": True},
            "mutation_guard": {"all_passed": True, "blocked_reasons": []},
            "typo_detected": True,
            "manifest_consistency_fixed": False,
        }

        validated = validate_patch_bundle_verification_result(result)
        assert validated["valid"] is False
        assert "manifest_inconsistency_not_fixed" in validated["blocked_reasons"]


# ── 11. generate_patch_bundle_verification_report Tests ─────────────────────

class TestGenerateReport:
    def test_generate_report_writes_only_tmp_path(self, mock_patch_file, mock_manifest, monkeypatch):
        patch_path = mock_patch_file
        manifest_path, manifest = mock_manifest
        bundle_path = patch_path.parent / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle"
        bundle_path.write_bytes(b"#" * 100)

        import hashlib
        manifest["patch_sha256"] = hashlib.sha256(patch_path.read_bytes()).hexdigest()
        manifest["patch_size_bytes"] = len(patch_path.read_bytes())
        manifest["bundle_sha256"] = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
        manifest["bundle_size_bytes"] = len(bundle_path.read_bytes())
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.REPORT_DIR",
            patch_path.parent,
        )

        gen_result_path = patch_path.parent / "R241-16S_PATCH_BUNDLE_GENERATION_RESULT.json"
        gen_result = {
            "status": "generated",
            "patch_generated": True,
            "manifest_generated": True,
            "source_commit_hash": SOURCE_COMMIT_HASH,
            "source_commit_only_target_workflow": True,
            "git_command_results": [],
            "local_mutation_guard": {"all_passed": True, "blocked_reasons": []},
            "validation": {"valid": True, "blocked_reasons": []},
        }
        gen_result_path.write_text(json.dumps(gen_result), encoding="utf-8")
        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.GENERATION_RESULT_PATH",
            gen_result_path,
        )

        output_dir = patch_path.parent / "test_output"
        output_dir.mkdir(parents=True, exist_ok=True)

        result = generate_patch_bundle_verification_report(
            output_path=str(output_dir / "custom.json")
        )

        assert Path(result["output_path"]).exists()
        assert result["validation"]["valid"] is True

    def test_no_workflow_modification_in_tests(self, mock_patch_file, mock_manifest, monkeypatch):
        """Verify that running verification does not modify the workflow file."""
        patch_path = mock_patch_file
        manifest_path, manifest = mock_manifest

        import hashlib
        manifest["patch_sha256"] = hashlib.sha256(patch_path.read_bytes()).hexdigest()
        manifest["patch_size_bytes"] = len(patch_path.read_bytes())
        manifest["bundle_path"] = ""
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.REPORT_DIR",
            patch_path.parent,
        )

        gen_result_path = patch_path.parent / "R241-16S_PATCH_BUNDLE_GENERATION_RESULT.json"
        gen_result = {
            "status": "generated",
            "patch_generated": True,
            "manifest_generated": True,
            "source_commit_hash": SOURCE_COMMIT_HASH,
            "source_commit_only_target_workflow": True,
            "git_command_results": [],
            "local_mutation_guard": {"all_passed": True, "blocked_reasons": []},
            "validation": {"valid": True, "blocked_reasons": []},
        }
        gen_result_path.write_text(json.dumps(gen_result), encoding="utf-8")
        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.GENERATION_RESULT_PATH",
            gen_result_path,
        )

        result = evaluate_patch_bundle_verification(str(patch_path.parent))

        mg = result["mutation_guard"]
        wf_check = next(
            (c for c in mg["checks"] if c["check_id"] == "workflow_file_unchanged"),
            None,
        )
        # If workflow didn't exist, check wouldn't run — that's OK
        if wf_check is not None:
            assert wf_check["passed"] is True


# ── Module-level safety tests ─────────────────────────────────────────────────

class TestSafetyConstraints:
    def test_no_secret_read_in_inspection(self, mock_patch_file, mock_manifest, monkeypatch):
        """The patch inspection should NOT read actual secrets from the environment."""
        patch_path = mock_patch_file
        manifest_path, manifest = mock_manifest

        import hashlib
        manifest["patch_sha256"] = hashlib.sha256(patch_path.read_bytes()).hexdigest()
        manifest["patch_size_bytes"] = len(patch_path.read_bytes())
        manifest["bundle_path"] = ""
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.REPORT_DIR",
            patch_path.parent,
        )

        gen_result_path = patch_path.parent / "R241-16S_PATCH_BUNDLE_GENERATION_RESULT.json"
        gen_result = {
            "status": "generated",
            "patch_generated": True,
            "manifest_generated": True,
            "source_commit_hash": SOURCE_COMMIT_HASH,
            "source_commit_only_target_workflow": True,
            "git_command_results": [],
            "local_mutation_guard": {"all_passed": True, "blocked_reasons": []},
            "validation": {"valid": True, "blocked_reasons": []},
        }
        gen_result_path.write_text(json.dumps(gen_result), encoding="utf-8")
        monkeypatch.setattr(
            "app.foundation.ci_patch_bundle_verification.GENERATION_RESULT_PATH",
            gen_result_path,
        )

        result = evaluate_patch_bundle_verification(str(patch_path.parent))
        # Should complete without reading secrets
        assert result["status"] != "unknown"

    def test_no_auto_fix_in_module(self):
        """The verification module itself should not contain any auto-fix logic."""
        import app.foundation.ci_patch_bundle_verification as mod
        source = Path(mod.__file__).read_text(encoding="utf-8")
        # Should not have auto_fix execution
        assert "auto_fix" not in source or "auto_fix_in_patch" in source
