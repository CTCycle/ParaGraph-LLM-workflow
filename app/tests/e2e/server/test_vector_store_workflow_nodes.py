from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

###############################################################################
def _vector_point(point_id: str, document_id: str, vector: list[float]) -> dict[str, object]:
    return {
        "id": point_id,
        "chunk_id": f"chunk-{point_id}",
        "document_id": document_id,
        "text": point_id,
        "source_uri": "local-test",
        "vector": vector,
        "embedding_provider": "fixture",
        "embedding_model": "fixture-v1",
        "embedding_revision": "r1",
        "normalized": False,
        "metadata": {"kind": "validation"},
    }

###############################################################################
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

###############################################################################
@pytest.mark.parametrize("provider", ["faiss", "lancedb", "chroma"])
def test_local_vector_store_lifecycle_runs_through_compiled_workflow(
    provider: str,
    client: TestClient,
    tmp_path: Path,
    wait_for_job,
) -> None:
    document_id = f"{provider}-document"
    point_ids = [f"{provider}-point-{index}" for index in range(2)]
    storage_path = tmp_path / provider
    definition = {
        "schema_version": 2,
        "nodes": [
            {
                "node_id": "point_batch",
                "node_type": "STRUCTURED_INPUT",
                "node_version": 1,
                "parameters": {
                    "value": [
                        _vector_point(point_ids[0], document_id, [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
                        _vector_point(point_ids[1], document_id, [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
                    ]
                },
            },
            {
                "node_id": "store_1",
                "node_type": "VECTOR_STORE",
                "node_version": 2,
                "parameters": {
                    "provider": provider,
                    "index_name": "pg-t3-local-vector",
                    "collection_name": "pg-t3-local-vector",
                    "distance_metric": "cosine",
                    "write_mode": "overwrite",
                    "id_conflict_policy": "upsert",
                    "storage_path": str(storage_path),
                },
            },
            {
                "node_id": "inspect_before_reload",
                "node_type": "VECTOR_STORE_LIFECYCLE",
                "node_version": 1,
                "parameters": {"operation": "inspect"},
            },
            {
                "node_id": "reload_1",
                "node_type": "VECTOR_STORE_LIFECYCLE",
                "node_version": 1,
                "parameters": {"operation": "reload"},
            },
            {
                "node_id": "inspect_after_reload",
                "node_type": "VECTOR_STORE_LIFECYCLE",
                "node_version": 1,
                "parameters": {"operation": "inspect"},
            },
            {
                "node_id": "delete_document",
                "node_type": "VECTOR_STORE_LIFECYCLE",
                "node_version": 1,
                "parameters": {
                    "operation": "delete_document",
                    "document_id": document_id,
                },
            },
            {
                "node_id": "inspect_after_delete",
                "node_type": "VECTOR_STORE_LIFECYCLE",
                "node_version": 1,
                "parameters": {"operation": "inspect"},
            },
        ],
        "connections": [
            {
                "from_node": "point_batch",
                "from_output": "result",
                "to_node": "store_1",
                "to_input": "vectors",
            },
            {
                "from_node": "store_1",
                "connection_type": "controller",
                "from_controller": "store",
                "to_node": "inspect_before_reload",
                "to_controller": "store",
            },
            {
                "from_node": "inspect_before_reload",
                "connection_type": "controller",
                "from_controller": "store",
                "to_node": "reload_1",
                "to_controller": "store",
            },
            {
                "from_node": "reload_1",
                "connection_type": "controller",
                "from_controller": "store",
                "to_node": "inspect_after_reload",
                "to_controller": "store",
            },
            {
                "from_node": "inspect_after_reload",
                "connection_type": "controller",
                "from_controller": "store",
                "to_node": "delete_document",
                "to_controller": "store",
            },
            {
                "from_node": "delete_document",
                "connection_type": "controller",
                "from_controller": "store",
                "to_node": "inspect_after_delete",
                "to_controller": "store",
            },
        ],
        "metadata": {},
    }

    compile_response = client.post("/executions/compile", json={"definition": definition})
    assert compile_response.status_code == 200, compile_response.text
    compiled = compile_response.json()
    assert compiled["valid"] is True, compiled

    start_response = client.post(
        "/executions",
        json={
            "workflow_id": f"pg-t3-{provider}-vector-store",
            "execution_session_id": f"pg-t3-{provider}-vector-store-session",
            "plan": compiled["plan"],
        },
    )
    assert start_response.status_code == 202, start_response.text
    run_id = start_response.json()["run_id"]

    status = wait_for_job(str(run_id), 10.0)
    run_response = client.get(f"/executions/{run_id}")
    assert run_response.status_code == 200
    run = run_response.json()
    assert status["status"] == "completed", run
    assert run["status"] == "completed", run

    stored = _step_ports(run, "store_1")["summary"]
    assert stored["upserted_count"] == 2
    assert stored["stored_ids"] == point_ids
    if provider == "faiss":
        assert _step_ports(run, "store_1")["store"]["metadata"]["index_type"] == "flat"
    if provider == "lancedb":
        metadata = _step_ports(run, "store_1")["store"]["metadata"]
        assert metadata["vector_index_status"] == "created"
        assert metadata["vector_index_type"] == "IVF_FLAT"
        assert metadata["num_partitions"] == 1

    before_reload = _step_ports(run, "inspect_before_reload")["result"]
    assert before_reload["exists"] is True
    assert before_reload["count"] == 2

    reloaded = _step_ports(run, "reload_1")["result"]
    assert reloaded["metadata"]["count"] == 2
    after_reload = _step_ports(run, "inspect_after_reload")["result"]
    assert after_reload["exists"] is True
    assert after_reload["count"] == 2

    deleted = _step_ports(run, "delete_document")["result"]
    assert deleted["affected_count"] == 2
    assert set(deleted["affected_ids"]) == set(point_ids)

    after_delete = _step_ports(run, "inspect_after_delete")["result"]
    assert after_delete["count"] == 0
    assert after_delete["exists"] is (provider == "chroma")
