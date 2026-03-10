from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient

from ParaGraph.server.services.workflow import nodes as node_module


def build_prompt_to_output_definition() -> dict[str, object]:
    return {
        'schema_version': 2,
        'nodes': [
            {'node_id': 'prompt_1', 'node_type': 'PROMPT', 'node_version': 1, 'parameters': {'prompt_text': 'Hello graph'}},
            {'node_id': 'output_1', 'node_type': 'TEXT_OUTPUT', 'node_version': 1, 'parameters': {}},
        ],
        'connections': [
            {'from_node': 'prompt_1', 'from_output': 'text', 'to_node': 'output_1', 'to_input': 'text'},
        ],
        'metadata': {},
    }


def test_nodes_catalog_exposes_registry(client: TestClient) -> None:
    response = client.get('/nodes/catalog')

    assert response.status_code == 200
    payload = response.json()

    ids = {node['id'] for node in payload['nodes']}
    assert {'PROMPT', 'LLM_GENERATE', 'TEXT_OUTPUT'}.issubset(ids)


def test_nodes_import_persists_manifest(client: TestClient, monkeypatch, tmp_path: Path) -> None:
    node_dir = tmp_path / 'nodes'
    node_dir.mkdir(parents=True, exist_ok=True)
    for manifest in Path('ParaGraph/resources/nodes').glob('*.json'):
        (node_dir / manifest.name).write_text(manifest.read_text(encoding='utf-8'), encoding='utf-8')

    monkeypatch.setattr(node_module, 'NODE_ROOT', node_dir)
    node_module.node_registry.reload()

    response = client.post(
        '/nodes/import',
        json={
            'id': 'CUSTOM_ECHO',
            'version': 1,
            'name': 'Custom Echo',
            'category': 'processing',
            'description': 'Echo text through a custom manifest.',
            'inputs': [{'name': 'text', 'data_type': 'TEXT', 'required': True, 'accepts_multiple': False}],
            'outputs': [{'name': 'text', 'data_type': 'TEXT', 'required': True, 'accepts_multiple': False}],
            'parameters': [],
            'ui': {'default_width': 280, 'accent_color': '#ffffff', 'collapsed_by_default': False},
            'runtime': {'executor_key': 'template_format', 'cacheable': True, 'deterministic': True, 'side_effecting': False},
        },
    )

    assert response.status_code == 201
    assert response.json()['id'] == 'CUSTOM_ECHO'
    assert (node_dir / 'custom_echo_v1.json').exists()


def test_compile_endpoint_returns_diagnostics_for_type_mismatch(client: TestClient) -> None:
    response = client.post(
        '/executions/compile',
        json={
            'definition': {
                'schema_version': 2,
                'nodes': [
                    {'node_id': 'prompt_1', 'node_type': 'PROMPT', 'node_version': 1, 'parameters': {'prompt_text': 'Hello'}},
                    {'node_id': 'embed_1', 'node_type': 'EMBEDDING_MODEL', 'node_version': 1, 'parameters': {}},
                    {'node_id': 'output_1', 'node_type': 'TEXT_OUTPUT', 'node_version': 1, 'parameters': {}},
                ],
                'connections': [
                    {'from_node': 'prompt_1', 'from_output': 'text', 'to_node': 'embed_1', 'to_input': 'text'},
                    {'from_node': 'embed_1', 'from_output': 'embedding', 'to_node': 'output_1', 'to_input': 'text'},
                ],
                'metadata': {},
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['valid'] is False
    messages = [item['message'] for item in payload['diagnostics']]
    assert any('Type mismatch' in message for message in messages)


def test_workflow_crud_and_versions(client: TestClient) -> None:
    create_response = client.post(
        '/workflows',
        json={
            'name': 'Manifest Workflow',
            'definition': build_prompt_to_output_definition(),
            'visual_graph': {
                'schema_version': 2,
                'nodes': [
                    {'node_id': 'prompt_1', 'x': 120, 'y': 120, 'width': 320, 'height': 200, 'collapsed': False},
                    {'node_id': 'output_1', 'x': 480, 'y': 120, 'width': 280, 'height': 180, 'collapsed': False},
                ],
                'groups': [],
                'comments': [],
            },
        },
    )

    assert create_response.status_code == 201
    workflow_id = create_response.json()['workflow_id']

    get_response = client.get(f'/workflows/{workflow_id}')
    assert get_response.status_code == 200
    assert get_response.json()['definition']['schema_version'] == 2

    update_response = client.put(
        f'/workflows/{workflow_id}',
        json={
            'name': 'Manifest Workflow Updated',
            'definition': build_prompt_to_output_definition(),
            'visual_graph': {
                'schema_version': 2,
                'nodes': [
                    {'node_id': 'prompt_1', 'x': 140, 'y': 120, 'width': 320, 'height': 200, 'collapsed': False},
                    {'node_id': 'output_1', 'x': 520, 'y': 120, 'width': 280, 'height': 180, 'collapsed': False},
                ],
                'groups': [],
                'comments': [],
            },
        },
    )

    assert update_response.status_code == 200
    assert update_response.json()['latest_version'] == 2


def test_execution_events_are_recorded_for_workflow_run(
    client: TestClient,
    wait_for_job: Callable[[str, float], dict[str, object]],
) -> None:
    compile_response = client.post('/executions/compile', json={'definition': build_prompt_to_output_definition()})
    assert compile_response.status_code == 200
    plan = compile_response.json()['plan']

    start_response = client.post('/executions', json={'workflow_id': None, 'plan': plan})
    assert start_response.status_code == 202
    run_id = start_response.json()['run_id']

    final_status = wait_for_job(run_id)
    assert final_status['status'] == 'completed'

    events_response = client.get(f'/executions/{run_id}/events')
    assert events_response.status_code == 200
    event_types = [event['event_type'] for event in events_response.json()['events']]
    assert 'execution.queued' in event_types
    assert 'execution.started' in event_types
    assert 'execution.step.completed' in event_types
    assert 'execution.completed' in event_types
