import copy
import json

from backend.app.asset import asset_projection


def test_discover_asset_runtime_paths_missing_path_returns_warning(tmp_path):
    result = asset_projection.discover_asset_runtime_paths(str(tmp_path))

    assert result["missing_paths"]
    assert result["warnings"]


def test_load_asset_registry_snapshot_missing_file_returns_warning(tmp_path):
    result = asset_projection.load_asset_registry_snapshot(str(tmp_path / "missing.json"))

    assert result["exists"] is False
    assert result["warnings"]


def test_load_asset_registry_snapshot_malformed_json_returns_warning(tmp_path):
    p = tmp_path / "asset_registry.json"
    p.write_text("{bad", encoding="utf-8")

    result = asset_projection.load_asset_registry_snapshot(str(p))

    assert result["exists"] is True
    assert result["asset_count"] == 0
    assert result["warnings"]


def test_load_asset_registry_snapshot_reads_records(tmp_path):
    p = tmp_path / "asset_registry.json"
    p.write_text(json.dumps({"assets": [{"id": "a1", "name": "tool asset"}]}), encoding="utf-8")

    result = asset_projection.load_asset_registry_snapshot(str(p))

    assert result["asset_count"] == 1
    assert result["registry_format"] == "dict.assets"
    assert "id" in result["sample_keys"]


def test_load_binding_report_snapshot_missing_file_not_failure(tmp_path):
    result = asset_projection.load_binding_report_snapshot(str(tmp_path / "missing_binding.json"))

    assert result["exists"] is False
    assert result["warnings"]


def test_project_registry_assets_projects_record(monkeypatch):
    monkeypatch.setattr(
        asset_projection,
        "load_asset_registry_snapshot",
        lambda: {
            "source_path": "asset_registry.json",
            "records": [{"id": "a1", "name": "tool executor asset", "metadata": {"success_rate": 0.8}}],
            "warnings": [],
        },
    )

    result = asset_projection.project_registry_assets()

    assert result["projected_count"] == 1
    assert result["projected_assets"][0]["asset_id"] == "a1"


def test_project_binding_assets_tool_binding_to_a1(monkeypatch):
    monkeypatch.setattr(
        asset_projection,
        "load_binding_report_snapshot",
        lambda: {
            "source_path": "binding_report.json",
            "records": [{"tool": "github_cli", "binding": "platform"}],
            "warnings": [],
        },
    )

    result = asset_projection.project_binding_assets()

    assert result["by_asset_category"]["A1_tool_capability"] == 1


def test_project_governance_asset_outcomes_uses_monkeypatch(monkeypatch):
    monkeypatch.setattr(
        asset_projection,
        "_load_governance_records_readonly",
        lambda: (
            [{"outcome_type": "asset_promotion", "actual": 1.0, "context": {"asset_id": "a1", "score": 88}}],
            [],
        ),
    )

    result = asset_projection.project_governance_asset_outcomes()

    assert result["asset_related_count"] == 1
    assert result["projected_count"] == 1


def test_aggregate_asset_projection_keeps_memory_candidates_candidate(monkeypatch):
    monkeypatch.setattr(asset_projection, "project_registry_assets", lambda limit=200: {"projected_assets": [], "projected_count": 0, "warnings": []})
    monkeypatch.setattr(asset_projection, "project_binding_assets", lambda limit=200: {"projected_assets": [], "projected_count": 0, "warnings": []})
    monkeypatch.setattr(asset_projection, "project_governance_asset_outcomes", lambda limit=200: {"projected_assets": [], "projected_count": 0, "warnings": []})
    monkeypatch.setattr(
        asset_projection,
        "_load_memory_candidate_projection",
        lambda: {"candidate_count": 1, "candidates": [{"lifecycle_tier": "candidate", "asset_category": "A5_cognitive_method"}], "warnings": []},
    )

    result = asset_projection.aggregate_asset_projection()

    assert result["candidate_count"] == 1
    assert result["formal_asset_count"] == 0


def test_detect_asset_projection_risks_registry_missing_missing_score_unverified():
    projection = {
        "registry_projection": {"projected_count": 0, "warnings": ["registry_missing:x"]},
        "binding_projection": {"projected_count": 0, "warnings": []},
        "governance_asset_projection": {"asset_related_count": 0, "projected_count": 0},
        "memory_candidate_projection": {"candidate_count": 0},
        "all_records": [
            {
                "asset_ref_id": "r1",
                "asset_category": "unknown",
                "lifecycle_tier": "candidate",
                "score": None,
                "verification_refs": [],
                "warnings": ["missing_score_components"],
            }
        ],
    }

    result = asset_projection.detect_asset_projection_risks(projection)

    assert result["risk_by_type"]["registry_missing"] == 1
    assert result["risk_by_type"]["missing_score_components"] >= 1
    assert result["risk_by_type"]["unverified_asset_candidate"] >= 1


def test_generate_asset_projection_report_writes_only_tmp_path(tmp_path, monkeypatch):
    output = tmp_path / "asset_projection.json"
    monkeypatch.setattr(asset_projection, "discover_asset_runtime_paths", lambda root=None: {"warnings": [], "discovered_paths": [], "missing_paths": []})
    monkeypatch.setattr(asset_projection, "load_asset_registry_snapshot", lambda path=None: {"warnings": [], "records": [], "asset_count": 0})
    monkeypatch.setattr(asset_projection, "load_binding_report_snapshot", lambda path=None: {"warnings": [], "records": [], "record_count": 0})
    monkeypatch.setattr(asset_projection, "project_registry_assets", lambda limit=200: {"projected_assets": [], "projected_count": 0, "warnings": []})
    monkeypatch.setattr(asset_projection, "project_binding_assets", lambda limit=200: {"projected_assets": [], "projected_count": 0, "warnings": []})
    monkeypatch.setattr(asset_projection, "project_governance_asset_outcomes", lambda limit=200: {"projected_assets": [], "projected_count": 0, "warnings": []})
    monkeypatch.setattr(asset_projection, "aggregate_asset_projection", lambda limit=200: {"risk_summary": {"warnings": []}, "warnings": []})

    result = asset_projection.generate_asset_projection_report(str(output))

    assert result["written"] is True
    assert output.exists()


def test_project_registry_assets_does_not_modify_input(monkeypatch):
    records = [{"id": "a1", "name": "tool executor asset", "metadata": {"success_rate": 0.8}}]
    original = copy.deepcopy(records)
    monkeypatch.setattr(
        asset_projection,
        "load_asset_registry_snapshot",
        lambda: {"source_path": "asset_registry.json", "records": records, "warnings": []},
    )

    asset_projection.project_registry_assets()

    assert records == original


def test_duplicate_candidate_diagnosed():
    projection = {
        "registry_projection": {"projected_count": 1, "warnings": []},
        "binding_projection": {"projected_count": 0, "warnings": []},
        "governance_asset_projection": {"asset_related_count": 0, "projected_count": 0},
        "memory_candidate_projection": {"candidate_count": 0},
        "all_records": [
            {"asset_id": "dup", "asset_category": "A1_tool_capability", "lifecycle_tier": "candidate", "verification_refs": []},
            {"asset_id": "dup", "asset_category": "A1_tool_capability", "lifecycle_tier": "candidate", "verification_refs": []},
        ],
    }

    result = asset_projection.detect_asset_projection_risks(projection)

    assert result["risk_by_type"]["duplicate_asset_candidate"] == 2


def test_unknown_asset_category_warning(monkeypatch):
    monkeypatch.setattr(
        asset_projection,
        "load_asset_registry_snapshot",
        lambda: {"source_path": "asset_registry.json", "records": [{"id": "x", "name": "blob"}], "warnings": []},
    )

    result = asset_projection.project_registry_assets()

    assert result["by_asset_category"]["unknown"] == 1
    assert "unknown_asset_category" in result["warnings"]
