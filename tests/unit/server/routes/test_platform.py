from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient


def test_nodes_catalog_exposes_registry(client: TestClient) -> None:
    response = client.get('/nodes/catalog')

    assert response.status_code == 200
    payload = response.json()

    types = {node['type'] for node in payload['nodes']}
    assert {'Prompt', 'LLM', 'Output'}.issubset(types)


def test_compile_endpoint_returns_diagnostics_for_unsupported_connected_nodes(client: TestClient) -> None:
    response = client.post(
        '/executions/compile',
        json={
            'definition': {
                'schema_version': 1,
                'nodes': [
                    {'node_id': 'retrieval_1', 'node_type': 'Retrieval', 'config': {}},
                    {'node_id': 'output_1', 'node_type': 'Output', 'config': {}},
                ],
                'edges': [
                    {
                        'edge_id': 'edge_1',
                        'source': {'node_id': 'retrieval_1', 'port': 'context_out'},
                        'target': {'node_id': 'output_1', 'port': 'text_in'},
                    }
                ],
                'metadata': {},
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['valid'] is False
    messages = [item['message'] for item in payload['diagnostics']]
    assert any('not supported by the MVP executor' in message for message in messages)


def test_workflow_crud_and_versions(client: TestClient) -> None:
    create_response = client.post(
        '/workflows',
        json={
            'name': 'Test Workflow',
            'definition': {
                'schema_version': 1,
                'nodes': [
                    {'node_id': 'output_1', 'node_type': 'Output', 'config': {}},
                ],
                'edges': [],
                'metadata': {},
            },
            'visual_graph': {
                'schema_version': 1,
                'nodes': [
                    {
                        'node_id': 'output_1',
                        'x': 120,
                        'y': 140,
                        'width': 280,
                        'height': 180,
                        'collapsed': False,
                    }
                ],
                'groups': [],
                'comments': [],
            },
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()
    workflow_id = created['workflow_id']

    get_response = client.get(f'/workflows/{workflow_id}')
    assert get_response.status_code == 200
    assert get_response.json()['workflow_id'] == workflow_id

    update_response = client.put(
        f'/workflows/{workflow_id}',
        json={
            'name': 'Test Workflow Updated',
            'definition': {
                'schema_version': 1,
                'nodes': [
                    {'node_id': 'output_1', 'node_type': 'Output', 'config': {'label': 'updated'}},
                ],
                'edges': [],
                'metadata': {},
            },
            'visual_graph': {
                'schema_version': 1,
                'nodes': [
                    {
                        'node_id': 'output_1',
                        'x': 200,
                        'y': 100,
                        'width': 280,
                        'height': 180,
                        'collapsed': False,
                    }
                ],
                'groups': [],
                'comments': [],
            },
        },
    )

    assert update_response.status_code == 200
    assert update_response.json()['latest_version'] == 2

    versions_response = client.get(f'/workflows/{workflow_id}/versions')
    assert versions_response.status_code == 200
    assert versions_response.json()['versions'] == [1, 2]


def test_execution_events_are_recorded_for_workflow_run(
    client: TestClient,
    wait_for_job: Callable[[str, float], dict[str, object]],
) -> None:
    response = client.post(
        '/workflow/execute',
        json={
            'nodes': [
                {'id': 'output_1', 'type': 'Output', 'position': {'x': 0, 'y': 0}, 'params': {}},
            ],
            'edges': [],
        },
    )

    assert response.status_code == 202
    run_id = response.json()['job_id']

    final_status = wait_for_job(run_id)
    assert final_status['status'] == 'completed'

    events_response = client.get(f'/executions/{run_id}/events')
    assert events_response.status_code == 200
    events = events_response.json()['events']
    event_types = [event['event_type'] for event in events]
    assert 'execution.queued' in event_types
    assert 'execution.started' in event_types
    assert 'execution.step.completed' in event_types
    assert 'execution.completed' in event_types