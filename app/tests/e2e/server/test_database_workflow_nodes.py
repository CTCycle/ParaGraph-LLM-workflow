from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from fastapi.testclient import TestClient


def _poll_run_until_terminal(
    client: TestClient, run_id: str, timeout_s: float = 3.0
) -> dict[str, object]:
    deadline = time.monotonic() + timeout_s
    last_payload: dict[str, object] | None = None
    while time.monotonic() < deadline:
        response = client.get(f"/executions/{run_id}")
        assert response.status_code == 200
        last_payload = response.json()
        if last_payload["status"] not in {"queued", "running"}:
            return last_payload
        time.sleep(0.01)
    raise AssertionError(f"Run {run_id} did not finish. Last payload: {last_payload}")


def _database_workflow_definition(database_path: Path) -> dict[str, object]:
    return {
        "schema_version": 2,
        "nodes": [
            {
                "node_id": "n00_db",
                "node_type": "SQL_FILE_DATABASE",
                "node_version": 1,
                "parameters": {"db_path": str(database_path), "db_connect_timeout": 30},
            },
            {
                "node_id": "n01_setup",
                "node_type": "CUSTOM_SQL_QUERY",
                "node_version": 1,
                "parameters": {
                    "sql": "create table qa_crud_nodes (id integer primary key, label text, status text, amount integer)"
                },
            },
            {
                "node_id": "n02_create",
                "node_type": "CRUD_CREATE",
                "node_version": 1,
                "parameters": {
                    "table": "qa_crud_nodes",
                    "values": {
                        "id": 1,
                        "label": "alpha",
                        "status": "new",
                        "amount": 10,
                    },
                },
            },
            {
                "node_id": "n03_read_created",
                "node_type": "CRUD_READ",
                "node_version": 1,
                "parameters": {
                    "table": "qa_crud_nodes",
                    "columns": "id,label,status,amount",
                    "filters": {"id": 1, "status": "new"},
                    "limit": 10,
                    "order_by": "id",
                },
            },
            {
                "node_id": "n04_update",
                "node_type": "CRUD_UPDATE",
                "node_version": 1,
                "parameters": {
                    "table": "qa_crud_nodes",
                    "values": {"status": "updated", "amount": 25},
                    "filters": {"id": 1, "status": "new"},
                },
            },
            {
                "node_id": "n05_custom_query",
                "node_type": "CUSTOM_SQL_QUERY",
                "node_version": 1,
                "parameters": {
                    "sql": "select status, count(*) as row_count, sum(amount) as total_amount, case when sum(amount) = 25 then 'pass' else 'fail' end as condition_result from qa_crud_nodes group by status"
                },
            },
            {
                "node_id": "n06_delete",
                "node_type": "CRUD_DELETE",
                "node_version": 1,
                "parameters": {"table": "qa_crud_nodes", "filters": {"id": 1}},
            },
            {
                "node_id": "n07_read_deleted",
                "node_type": "CRUD_READ",
                "node_version": 1,
                "parameters": {
                    "table": "qa_crud_nodes",
                    "columns": "id,label,status,amount",
                    "filters": {"id": 1},
                    "limit": 10,
                    "order_by": "id",
                },
            },
        ],
        "connections": [
            {
                "from_node": "n00_db",
                "connection_type": "controller",
                "from_controller": "connection",
                "to_node": node_id,
                "to_controller": "connection",
            }
            for node_id in [
                "n01_setup",
                "n02_create",
                "n03_read_created",
                "n04_update",
                "n05_custom_query",
                "n06_delete",
                "n07_read_deleted",
            ]
        ],
        "metadata": {},
    }


def _step_ports(run_payload: dict[str, object], node_id: str) -> dict[str, object]:
    steps = run_payload["steps"]
    assert isinstance(steps, list)
    for step in steps:
        assert isinstance(step, dict)
        if step["node_id"] == node_id:
            output = step["output"]
            assert isinstance(output, dict)
            ports = output["ports"]
            assert isinstance(ports, dict)
            return ports
    raise AssertionError(f"Missing step for node {node_id}")


def test_database_crud_nodes_execute_together_through_compiled_workflow(
    client: TestClient, tmp_path: Path
) -> None:
    database_path = tmp_path / "workflow-crud.sqlite"
    sqlite3.connect(database_path).close()
    definition = _database_workflow_definition(database_path)

    try:
        compile_response = client.post(
            "/executions/compile", json={"definition": definition}
        )
        assert compile_response.status_code == 200
        compiled = compile_response.json()
        assert compiled["valid"] is True

        start_response = client.post(
            "/executions",
            headers={"X-Request-ID": "qa-crud-workflow"},
            json={
                "workflow_id": "wf-crud",
                "execution_session_id": "session-crud",
                "plan": compiled["plan"],
            },
        )
        assert start_response.status_code == 202

        final_run = _poll_run_until_terminal(client, start_response.json()["run_id"])
        assert final_run["status"] == "completed", final_run
        assert final_run["request_id"] == "qa-crud-workflow"

        created = _step_ports(final_run, "n02_create")["dataset"]
        assert isinstance(created, dict)
        assert created["affected_rows"] == 1

        read_created = _step_ports(final_run, "n03_read_created")["dataset"]
        assert isinstance(read_created, dict)
        assert read_created["rows"] == [
            {"id": 1, "label": "alpha", "status": "new", "amount": 10}
        ]

        custom_query = _step_ports(final_run, "n05_custom_query")["dataset"]
        assert isinstance(custom_query, dict)
        assert custom_query["rows"] == [
            {
                "status": "updated",
                "row_count": 1,
                "total_amount": 25,
                "condition_result": "pass",
            }
        ]

        read_deleted = _step_ports(final_run, "n07_read_deleted")["dataset"]
        assert isinstance(read_deleted, dict)
        assert read_deleted["rows"] == []
    finally:
        if database_path.exists():
            with sqlite3.connect(database_path) as connection:
                connection.execute("drop table if exists qa_crud_nodes")
                connection.commit()
