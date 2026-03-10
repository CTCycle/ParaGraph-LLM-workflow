from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient


def build_simple_definition(prompt_text: str) -> dict[str, object]:
    return {
        'schema_version': 2,
        'nodes': [
            {'node_id': 'prompt_1', 'node_type': 'PROMPT', 'node_version': 1, 'parameters': {'prompt_text': prompt_text}},
            {'node_id': 'output_1', 'node_type': 'TEXT_OUTPUT', 'node_version': 1, 'parameters': {}},
        ],
        'connections': [
            {'from_node': 'prompt_1', 'from_output': 'text', 'to_node': 'output_1', 'to_input': 'text'},
        ],
        'metadata': {},
    }


def test_compile_returns_plan_for_supported_graph(client: TestClient) -> None:
    response = client.post('/executions/compile', json={'definition': build_simple_definition('Plan me')})

    assert response.status_code == 200
    payload = response.json()
    assert payload['valid'] is True
    assert payload['plan']['step_order'] == ['prompt_1', 'output_1']


def test_compile_rejects_cycles(client: TestClient) -> None:
    response = client.post(
        '/executions/compile',
        json={
            'definition': {
                'schema_version': 2,
                'nodes': [
                    {'node_id': 'if_1', 'node_type': 'IF', 'node_version': 1, 'parameters': {}},
                    {'node_id': 'router_1', 'node_type': 'ROUTER', 'node_version': 1, 'parameters': {}},
                ],
                'connections': [
                    {'from_node': 'if_1', 'from_output': 'result', 'to_node': 'router_1', 'to_input': 'value'},
                    {'from_node': 'router_1', 'from_output': 'matched', 'to_node': 'if_1', 'to_input': 'true_value'},
                ],
                'metadata': {},
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['valid'] is False
    assert any(item['code'] == 'graph_cycle' for item in payload['diagnostics'])


def test_execute_returns_run_and_persists_output_payload(
    client: TestClient,
    wait_for_job: Callable[[str, float], dict[str, object]],
) -> None:
    compile_response = client.post('/executions/compile', json={'definition': build_simple_definition('Persist me')})
    plan = compile_response.json()['plan']

    start_response = client.post('/executions', json={'workflow_id': None, 'plan': plan})

    assert start_response.status_code == 202
    run_id = start_response.json()['run_id']

    final_status = wait_for_job(str(run_id))
    status_response = client.get(f'/executions/{run_id}')

    assert final_status['status'] == 'completed'
    assert final_status['result'] == {'outputs': {'output_1': {'text': 'Persist me'}}}
    assert status_response.status_code == 200
    assert status_response.json()['outputs'] == {'output_1': {'text': 'Persist me'}}


def test_get_missing_execution_returns_not_found(client: TestClient) -> None:
    response = client.get('/executions/missing-run')

    assert response.status_code == 404
    assert response.json()['detail'] == 'Run not found: missing-run'
