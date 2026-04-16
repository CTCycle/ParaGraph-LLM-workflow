from __future__ import annotations

from fastapi.testclient import TestClient


def _definition() -> dict[str, object]:
    return {
        "schema_version": 2,
        "nodes": [
            {
                "node_id": "prompt_1",
                "node_type": "PROMPT",
                "node_version": 1,
                "parameters": {"prompt_text": "hello"},
            },
            {
                "node_id": "output_1",
                "node_type": "TEXT_OUTPUT",
                "node_version": 1,
                "parameters": {},
            },
        ],
        "connections": [
            {
                "from_node": "prompt_1",
                "from_output": "text",
                "to_node": "output_1",
                "to_input": "text",
            }
        ],
        "metadata": {},
    }


def _visual_graph() -> dict[str, object]:
    return {
        "schema_version": 2,
        "nodes": [
            {
                "node_id": "prompt_1",
                "x": 120,
                "y": 120,
                "width": 320,
                "height": 220,
                "collapsed": False,
            },
            {
                "node_id": "output_1",
                "x": 520,
                "y": 120,
                "width": 320,
                "height": 220,
                "collapsed": False,
            },
        ],
        "groups": [],
        "comments": [],
    }


def test_workflow_versions_list_for_existing_workflow(client: TestClient) -> None:
    create_response = client.post(
        "/workflows",
        json={
            "name": "Versioned workflow",
            "definition": _definition(),
            "visual_graph": _visual_graph(),
        },
    )
    assert create_response.status_code == 201
    workflow_id = create_response.json()["workflow_id"]

    versions_initial = client.get(f"/workflows/{workflow_id}/versions")
    assert versions_initial.status_code == 200
    assert versions_initial.json()["versions"] == [1]

    update_response = client.put(
        f"/workflows/{workflow_id}",
        json={
            "name": "Versioned workflow",
            "definition": _definition(),
            "visual_graph": _visual_graph(),
        },
    )
    assert update_response.status_code == 200

    versions_updated = client.get(f"/workflows/{workflow_id}/versions")
    assert versions_updated.status_code == 200
    assert versions_updated.json()["versions"] == [1, 2]


def test_workflow_versions_returns_404_for_missing_workflow(client: TestClient) -> None:
    response = client.get("/workflows/wf_missing/versions")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workflow not found: wf_missing"
