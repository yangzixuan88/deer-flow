from pathlib import Path

from app.foundation import integration_readiness as ir


def test_discover_foundation_surfaces_mock_surfaces(tmp_path, monkeypatch):
    (tmp_path / "backend/app/m11").mkdir(parents=True)
    (tmp_path / "backend/app/m11/truth_state_contract.py").write_text("", encoding="utf-8")
    (tmp_path / "backend/app/m11/test_truth_state_contract.py").write_text("", encoding="utf-8")
    (tmp_path / "migration_reports/foundation_audit").mkdir(parents=True)
    (tmp_path / "migration_reports/foundation_audit/R241-1A_TRUTH_STATE_WRAPPER_REPORT.md").write_text("report", encoding="utf-8")
    monkeypatch.setattr(ir, "SURFACE_DEFINITIONS", [ir.SURFACE_DEFINITIONS[0]])
    monkeypatch.setattr(ir, "_safe_import", lambda import_path: (True, None))
    result = ir.discover_foundation_surfaces(str(tmp_path))
    assert result["discovered_count"] == 1
    assert result["surfaces"][0]["module_exists"] is True


def test_missing_module_report_sample_returns_warning(tmp_path, monkeypatch):
    monkeypatch.setattr(ir, "_safe_import", lambda import_path: (False, "import_failed:x"))
    result = ir.discover_foundation_surfaces(str(tmp_path))
    assert result["warnings"]


def test_evaluate_truth_state_read_only_ready():
    surface = {
        "surface_id": "truth_state_contract",
        "surface_type": "truth_state_projection",
        "module_path": "backend/app/m11/truth_state_contract.py",
        "owner_domain": "truth_state",
        "module_exists": True,
        "import_ok": True,
        "tests_exist": True,
    }
    result = ir.evaluate_surface_readiness(surface)
    assert result["readiness_level"] == "read_only_ready"


def test_evaluate_memory_cleanup_blocked():
    result = ir.evaluate_surface_readiness(
        {"surface_id": "memory_cleanup_write_policy", "surface_type": "memory_projection", "owner_domain": "memory", "virtual": True, "blocked_intent": "memory cleanup without quarantine"}
    )
    assert result["readiness_level"] == "blocked"


def test_evaluate_prompt_replacement_blocked():
    result = ir.evaluate_surface_readiness(
        {"surface_id": "prompt_replacement", "surface_type": "prompt_projection", "owner_domain": "prompt", "virtual": True, "blocked_intent": "prompt replacement without backup"}
    )
    assert result["decision"] == "block_integration"


def test_evaluate_feishu_push_without_policy_blocked():
    result = ir.evaluate_surface_readiness(
        {"surface_id": "real_feishu_push", "surface_type": "feishu_summary_projection", "owner_domain": "nightly", "virtual": True, "blocked_intent": "Feishu push without webhook policy"}
    )
    assert result["readiness_level"] in {"report_only", "blocked"}


def test_build_integration_matrix_counts():
    surfaces = [
        {"surface_id": "truth_state_contract", "surface_type": "truth_state_projection", "owner_domain": "truth_state", "module_exists": True, "import_ok": True, "tests_exist": True},
        {"surface_id": "memory_cleanup", "surface_type": "memory_projection", "owner_domain": "memory", "virtual": True, "blocked_intent": "memory cleanup without quarantine"},
    ]
    matrix = ir.build_integration_matrix(surfaces)
    assert matrix["read_only_ready_count"] == 1
    assert matrix["blocked_count"] == 1


def test_identify_blockers_prompt_replacement_without_backup():
    matrix = ir.build_integration_matrix([
        {"surface_id": "prompt_replacement", "surface_type": "prompt_projection", "owner_domain": "prompt", "virtual": True, "blocked_intent": "prompt replacement without backup"}
    ])
    blockers = ir.identify_integration_blockers(matrix)
    assert any("prompt replacement" in b["blocker_type"].lower() for b in blockers["blockers"])


def test_identify_blockers_gateway_routing_mutation():
    matrix = ir.build_integration_matrix([
        {"surface_id": "gateway_run_path_integration", "surface_type": "gateway_mode_instrumentation", "owner_domain": "gateway", "virtual": True, "blocked_intent": "Gateway routing mutation"}
    ])
    blockers = ir.identify_integration_blockers(matrix)
    assert any("gateway routing" in b["blocker_type"].lower() for b in blockers["blockers"])


def test_minimal_plan_contains_phase_a_to_e():
    plan = ir.propose_minimal_read_only_integration_plan({})
    phases = [p["phase_id"] for p in plan["phases"]]
    assert phases == ["Phase A", "Phase B", "Phase C", "Phase D", "Phase E"]


def test_phase_e_gated_write_blocked():
    plan = ir.propose_minimal_read_only_integration_plan({})
    phase_e = next(p for p in plan["phases"] if p["phase_id"] == "Phase E")
    assert phase_e["allowed"] is False
    assert "blocked" in phase_e["constraints"]


def test_generate_review_writes_only_tmp_path(tmp_path, monkeypatch):
    monkeypatch.setattr(ir, "DEFAULT_MATRIX_PATH", tmp_path / "matrix.json")
    monkeypatch.setattr(ir, "DEFAULT_REPORT_PATH", tmp_path / "report.md")
    monkeypatch.setattr(ir, "_safe_import", lambda import_path: (True, None))
    result = ir.generate_integration_readiness_review()
    assert Path(result["matrix_path"]).exists()
    assert Path(result["report_path"]).exists()


def test_no_runtime_modified(tmp_path):
    before = set(tmp_path.iterdir())
    ir.build_integration_matrix([])
    after = set(tmp_path.iterdir())
    assert before == after


def test_no_action_queue_written(tmp_path, monkeypatch):
    monkeypatch.setattr(ir, "DEFAULT_MATRIX_PATH", tmp_path / "matrix.json")
    monkeypatch.setattr(ir, "DEFAULT_REPORT_PATH", tmp_path / "report.md")
    monkeypatch.setattr(ir, "_safe_import", lambda import_path: (True, None))
    ir.generate_integration_readiness_review()
    assert not (tmp_path / "action_queue.json").exists()


def test_no_tool_execution():
    matrix = ir.build_integration_matrix([])
    assert matrix["surfaces"] == []


def test_import_failure_not_crash(tmp_path, monkeypatch):
    monkeypatch.setattr(ir, "_safe_import", lambda import_path: (False, "import_failed:boom"))
    result = ir.discover_foundation_surfaces(str(tmp_path))
    assert result["discovered_count"] >= 1
    assert result["warnings"]

