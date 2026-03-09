from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient


###############################################################################
def test_get_workflow_catalog_returns_expected_nodes(client: TestClient) -> None:
    response = client.get("/workflow/catalog")

    assert response.status_code == 200
    payload = response.json()

    assert [node["type"] for node in payload["nodes"]] == [
        "Prompt",
        "LLM",
        "Retrieval",
        "VectorDB",
        "Output",
    ]


# -----------------------------------------------------------------------------
def test_validate_rejects_connected_placeholder_nodes(client: TestClient) -> None:
    response = client.post(
        "/workflow/validate",
        json={
            "nodes": [
                {"id": "retrieval_1", "type": "Retrieval", "position": {"x": 0, "y": 0}, "params": {}},
                {"id": "output_1", "type": "Output", "position": {"x": 200, "y": 0}, "params": {}},
            ],
            "edges": [
                {
                    "id": "edge_1",
                    "source": "retrieval_1",
                    "sourceHandle": "context_out",
                    "target": "output_1",
                    "targetHandle": "text_in",
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["valid"] is False
    assert any("not supported by the MVP executor" in error for error in payload["errors"])


# -----------------------------------------------------------------------------
def test_execute_returns_job_and_persists_output_payload(
    client: TestClient,
    wait_for_job: Callable[[str, float], dict[str, object]],
) -> None:
    response = client.post(
        "/workflow/execute",
        json={
            "nodes": [
                {"id": "output_1", "type": "Output", "position": {"x": 0, "y": 0}, "params": {}},
            ],
            "edges": [],
        },
    )

    assert response.status_code == 202
    payload = response.json()

    assert payload["job_type"] == "workflow"
    assert payload["output_node_ids"] == ["output_1"]

    final_status = wait_for_job(str(payload["job_id"]))
    status_response = client.get(f"/workflow/jobs/{payload['job_id']}")

    assert final_status["status"] == "completed"
    assert final_status["result"] == {"outputs": {"output_1": {"text": ""}}}
    assert status_response.status_code == 200
    assert status_response.json()["result"] == {"outputs": {"output_1": {"text": ""}}}


# -----------------------------------------------------------------------------
def test_get_missing_workflow_job_returns_not_found(client: TestClient) -> None:
    response = client.get("/workflow/jobs/missing-job")

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found: missing-job"
