import json
from pathlib import Path

from app.foundation import read_only_integration_plan as plan


def _matrix():
    return {
        "surfaces": [
            {"surface_id": "truth_state_contract", "readiness_level": "read_only_ready", "surface_type": "truth_state_projection"},
            {"surface_id": "memory_cleanup_write_policy", "readiness_level": "blocked", "surface_type": "memory_projection"},
            {"surface_id": "queue_sandbox_truth_projection", "readiness_level": "read_only_ready", "surface_type": "queue_sandbox_projection", "warnings": ["queue_path_mismatch_unresolved"]},
        ],
        "read_only_ready_count": 2,
        "blocked_count": 1,
    }


def test_load_readiness_matrix_missing_file_warning(tmp_path):
    result = plan.load_readiness_matrix(str(tmp_path / "missing.json"))
    assert result["exists"] is False
    assert result["warnings"]


def test_load_readiness_matrix_malformed_json_warning(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{bad", encoding="utf-8")
    result = plan.load_readiness_matrix(str(p))
    assert result["exists"] is True
    assert result["warnings"]


def test_extract_readonly_surfaces_only_read_only_ready():
    result = plan.extract_readonly_surfaces(_matrix())
    assert len(result["approved_surfaces"]) == 2
    assert all(s["readiness_level"] == "read_only_ready" for s in result["approved_surfaces"])


def test_blocked_surfaces_not_approved():
    result = plan.extract_readonly_surfaces(_matrix())
    ids = {s["surface_id"] for s in result["approved_surfaces"]}
    assert "memory_cleanup_write_policy" not in ids
    assert result["blocked_surfaces"]


def test_build_cli_command_specs_contains_nine_commands():
    specs = plan.build_cli_command_specs([])
    assert specs["command_count"] == 9
    names = {s["command_name"] for s in specs["command_specs"]}
    assert "foundation diagnose all" in names


def test_build_api_endpoint_specs_contains_nine_get_endpoints():
    specs = plan.build_api_endpoint_specs([])
    assert specs["endpoint_count"] == 9
    assert all(s["method"] == "GET" for s in specs["endpoint_specs"])


def test_all_endpoints_write_runtime_false():
    specs = plan.build_api_endpoint_specs([])
    assert all(s["writes_runtime"] is False for s in specs["endpoint_specs"])


def test_all_endpoints_disabled_by_default():
    specs = plan.build_api_endpoint_specs([])
    assert all(s["disabled_by_default"] is True for s in specs["endpoint_specs"])


def test_all_endpoints_require_auth_later():
    specs = plan.build_api_endpoint_specs([])
    assert all(s["requires_auth_later"] is True for s in specs["endpoint_specs"])


def test_feishu_summary_dry_run_only():
    specs = plan.build_cli_command_specs([])
    feishu = next(s for s in specs["command_specs"] if s["surface"] == "feishu_summary")
    assert feishu["permission"] == "dry_run_only"


def test_validate_blocks_post_put_delete():
    p = {"cli_command_specs": [], "api_endpoint_specs": [{"method": "POST", "path": "/x", "writes_runtime": False, "disabled_by_default": True, "requires_auth_later": True, "requires_rate_limit_later": True}], "blocked_surfaces": []}
    result = plan.validate_readonly_integration_plan(p)
    assert result["valid"] is False
    assert any("mutating_endpoint_method" in e for e in result["errors"])


def test_validate_blocks_blocked_surface():
    p = {
        "cli_command_specs": [{"command_name": "bad", "surface": "blocked", "writes_runtime": False}],
        "api_endpoint_specs": [],
        "blocked_surfaces": [{"surface_id": "blocked", "surface": "blocked"}],
    }
    result = plan.validate_readonly_integration_plan(p)
    assert result["valid"] is False


def test_queue_path_mismatch_warning_only():
    specs = plan.build_cli_command_specs([])
    p = {"cli_command_specs": specs["command_specs"], "api_endpoint_specs": plan.build_api_endpoint_specs([])["endpoint_specs"], "blocked_surfaces": []}
    result = plan.validate_readonly_integration_plan(p)
    assert "queue_path_mismatch_unresolved" in result["warnings"]


def test_implementation_sequence_contains_sidecar_not_main_run_path():
    seq = plan.build_implementation_sequence({})
    text = " ".join(step["step"] for step in seq["sequence"])
    assert "sidecar router" in text
    assert "not main run path" in text


def test_generate_plan_writes_only_tmp_path(tmp_path, monkeypatch):
    matrix_path = tmp_path / "matrix.json"
    matrix_path.write_text(json.dumps({"matrix": _matrix()}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(plan, "DEFAULT_MATRIX_PATH", matrix_path)
    result = plan.generate_minimal_readonly_integration_plan(output_path=str(tmp_path / "plan.json"))
    assert Path(result["json_path"]).exists()
    assert Path(result["markdown_path"]).exists()


def test_no_runtime_modified(tmp_path):
    before = set(tmp_path.iterdir())
    plan.build_cli_command_specs([])
    plan.build_api_endpoint_specs([])
    after = set(tmp_path.iterdir())
    assert before == after


def test_no_action_queue_written(tmp_path, monkeypatch):
    matrix_path = tmp_path / "matrix.json"
    matrix_path.write_text(json.dumps({"matrix": _matrix()}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(plan, "DEFAULT_MATRIX_PATH", matrix_path)
    plan.generate_minimal_readonly_integration_plan(output_path=str(tmp_path / "plan.json"))
    assert not (tmp_path / "action_queue.json").exists()


def test_no_tool_execution():
    validation = plan.validate_readonly_integration_plan({"cli_command_specs": [], "api_endpoint_specs": [], "blocked_surfaces": []})
    assert "missing_cli_command_specs" in validation["errors"]

