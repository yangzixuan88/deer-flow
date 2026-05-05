"""Tests for app.m04.registry_manager — Upgrade Center / experiment_queue registry."""

import sqlite3

from app.m04.registry_db import init_registry_db
from app.m04.registry_manager import RegistryManager


class TestRegistryManagerWorkflows:
    """Tests for workflow CRUD operations."""

    def test_save_workflow_returns_flow_id(self, tmp_path):
        db = tmp_path / "test_registry.db"
        init_registry_db(str(db))
        manager = RegistryManager(db_path=str(db))

        flow_id = manager.save_workflow(
            name="test-flow",
            category="test",
            sop_source="test source",
            nodes={"nodes": []},
            edges={"edges": []},
            risk_level="low",
            cost_estimate={"cost": 1},
        )

        assert flow_id is not None
        assert flow_id.startswith("flow_")

    def test_save_workflow_persists_to_db(self, tmp_path):
        db = tmp_path / "test_registry.db"
        init_registry_db(str(db))
        manager = RegistryManager(db_path=str(db))

        flow_id = manager.save_workflow(
            name="persist-test",
            category="persist",
            sop_source="source content",
            nodes={"key": "node"},
            edges={"key": "edge"},
            risk_level="medium",
            cost_estimate=None,
        )

        # Verify data was written to DB
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM workflows WHERE flow_id=?", (flow_id,)).fetchone()
        conn.close()

        assert row is not None
        assert row["name"] == "persist-test"
        assert row["category"] == "persist"
        assert row["risk_level"] == "medium"

    def test_get_workflow_returns_deserialized_record(self, tmp_path):
        db = tmp_path / "test_registry.db"
        init_registry_db(str(db))
        manager = RegistryManager(db_path=str(db))

        flow_id = manager.save_workflow(
            name="roundtrip-test",
            category="roundtrip",
            sop_source="source",
            nodes={"n1": {"id": "a"}},
            edges={"e1": {"from": "a", "to": "b"}},
            risk_level="low",
            cost_estimate={"tokens": 100},
        )

        result = manager.get_workflow(flow_id)

        assert result is not None
        assert result["flow_id"] == flow_id
        assert result["name"] == "roundtrip-test"
        # JSON fields should be deserialized
        assert result["nodes_json"] == {"n1": {"id": "a"}}
        assert result["edges_json"] == {"e1": {"from": "a", "to": "b"}}
        assert result["cost_estimate_json"] == {"tokens": 100}

    def test_get_workflow_returns_none_for_missing(self, tmp_path):
        db = tmp_path / "test_registry.db"
        init_registry_db(str(db))
        manager = RegistryManager(db_path=str(db))

        result = manager.get_workflow("nonexistent_flow_00000000")

        assert result is None

    def test_save_workflow_multiple_workflows_distinct_ids(self, tmp_path):
        db = tmp_path / "test_registry.db"
        init_registry_db(str(db))
        manager = RegistryManager(db_path=str(db))

        id1 = manager.save_workflow("wf1", "cat", "src", {}, {})
        id2 = manager.save_workflow("wf2", "cat", "src", {}, {})
        id3 = manager.save_workflow("wf3", "cat", "src", {}, {})

        assert id1 != id2 != id3
        assert len({id1, id2, id3}) == 3


class TestRegistryManagerTasks:
    """Tests for task CRUD operations."""

    def test_save_task_returns_task_id(self, tmp_path):
        db = tmp_path / "test_registry.db"
        init_registry_db(str(db))
        manager = RegistryManager(db_path=str(db))

        task_id = manager.save_task(
            goal="complete the thing",
            dag={"steps": ["step1", "step2"]},
            total_tokens=500,
        )

        assert task_id is not None
        assert task_id.startswith("task_")

    def test_save_task_persists_to_db(self, tmp_path):
        db = tmp_path / "test_registry.db"
        init_registry_db(str(db))
        manager = RegistryManager(db_path=str(db))

        task_id = manager.save_task(
            goal="test goal",
            dag={"action": "do thing"},
            total_tokens=0,
        )

        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        conn.close()

        assert row is not None
        assert row["goal"] == "test goal"
        assert row["status"] == "pending"
        assert row["dag_json"] == '{"action": "do thing"}'

    def test_update_task_status(self, tmp_path):
        db = tmp_path / "test_registry.db"
        init_registry_db(str(db))
        manager = RegistryManager(db_path=str(db))

        task_id = manager.save_task("goal", {"step": "a"}, 0)
        manager.update_task_status(task_id, "running", additional_tokens=100)

        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT status, total_tokens FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        conn.close()

        assert row is not None
        assert row["status"] == "running"
        assert row["total_tokens"] == 100

    def test_update_task_status_nonexistent_does_not_raise(self, tmp_path):
        db = tmp_path / "test_registry.db"
        init_registry_db(str(db))
        manager = RegistryManager(db_path=str(db))

        # Should not raise, just logs error
        manager.update_task_status("nonexistent_task_00000000", "done")


class TestRegistryManagerSchema:
    """Tests for database schema initialization."""

    def test_init_registry_db_creates_required_tables(self, tmp_path):
        db = tmp_path / "init_test.db"
        init_registry_db(str(db))

        # Verify all tables exist
        conn = sqlite3.connect(str(db))
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()

        assert "workflows" in tables
        assert "tasks" in tables
        assert "search_assets" in tables
        assert "boulder_records" in tables


class TestRegistryManagerErrorHandling:
    """Tests for error handling and edge cases."""

    def test_manager_with_invalid_db_path_does_not_crash_init(self, tmp_path):
        """Manager instantiation should not fail even with unusual path."""
        manager = RegistryManager(db_path=str(tmp_path / "newdir" / "nonexistent.db"))
        assert manager.db_path is not None

    def test_save_workflow_with_empty_strings(self, tmp_path):
        """Empty strings for optional fields should be handled gracefully."""
        db = tmp_path / "test.db"
        init_registry_db(str(db))
        manager = RegistryManager(db_path=str(db))

        flow_id = manager.save_workflow(
            name="",
            category="",
            sop_source="",
            nodes={},
            edges={},
        )

        # Should still get a valid flow_id
        assert flow_id is not None

    def test_workflow_json_fields_accept_empty_dict(self, tmp_path):
        """Nodes and edges as empty dicts should serialize cleanly."""
        db = tmp_path / "test.db"
        init_registry_db(str(db))
        manager = RegistryManager(db_path=str(db))

        flow_id = manager.save_workflow(
            name="empty-json-test",
            category="test",
            sop_source="src",
            nodes={},
            edges={},
        )

        result = manager.get_workflow(flow_id)
        assert result["nodes_json"] == {}
        assert result["edges_json"] == {}
