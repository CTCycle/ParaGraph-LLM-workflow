from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient



def build_fragmentation_definition(source_path: str, output_path: str) -> dict[str, object]:
    source_folder = str(Path(source_path).resolve().parent)
    return {
        'schema_version': 2,
        'nodes': [
            {
                'node_id': 'doc_1',
                'node_type': 'LOAD_DOCUMENTS',
                'node_version': 1,
                'parameters': {'folder_path': source_folder, 'recursive': False},
            },
            {
                'node_id': 'split_1',
                'node_type': 'BY_DELIMITER_CHUNKS',
                'node_version': 1,
                'parameters': {
                    'delimiter': 'period',
                    'keep_delimiter': False,
                    'drop_empty': True,
                    'max_chunk_size': 0,
                    'overflow_strategy': 'split_further',
                },
            },
            {
                'node_id': 'merge_1',
                'node_type': 'MERGE_SMALL_CHUNKS',
                'node_version': 1,
                'parameters': {
                    'target_chunk_size': 8,
                    'unit': 'words',
                    'max_chunk_size': 0,
                    'merge_strategy': 'sequential',
                    'preserve_boundaries': True,
                },
            },
            {
                'node_id': 'save_1',
                'node_type': 'SAVE_AS_FOLDER',
                'node_version': 1,
                'parameters': {
                    'output_path': output_path,
                    'extension': '.md',
                },
            },
            {'node_id': 'output_1', 'node_type': 'JSON_OUTPUT', 'node_version': 1, 'parameters': {}},
        ],
        'connections': [
            {'from_node': 'doc_1', 'from_output': 'documents', 'to_node': 'split_1', 'to_input': 'documents'},
            {'from_node': 'split_1', 'from_output': 'chunks', 'to_node': 'merge_1', 'to_input': 'chunks'},
            {'from_node': 'merge_1', 'from_output': 'chunks', 'to_node': 'save_1', 'to_input': 'chunks'},
            {'from_node': 'save_1', 'from_output': 'artifact', 'to_node': 'output_1', 'to_input': 'value'},
        ],
        'metadata': {},
    }



def test_execute_fragmentation_pipeline_returns_serialization_artifact(
    client: TestClient,
    tmp_path: Path,
    wait_for_job,
) -> None:
    source = tmp_path / 'fragment-source.txt'
    source.write_text('Apples are crisp. Bananas are softer. Carrots are crunchy.', encoding='utf-8')
    export_target = tmp_path / 'exports' / 'fragments'

    compile_response = client.post(
        '/executions/compile',
        json={'definition': build_fragmentation_definition(str(source), str(export_target))},
    )
    assert compile_response.status_code == 200
    payload = compile_response.json()
    assert payload['valid'] is True

    start_response = client.post('/executions', json={'workflow_id': None, 'plan': payload['plan']})
    assert start_response.status_code == 202
    run_id = start_response.json()['run_id']

    final_status = wait_for_job(str(run_id), 3.0)
    run_payload = client.get(f'/executions/{run_id}').json()

    assert final_status['status'] == 'completed'
    artifact = run_payload['outputs']['output_1']['json']
    assert artifact['extension'] == '.md'
    assert artifact['count'] >= 1

    written_files = [Path(path) for path in artifact['files']]
    assert all(path.exists() for path in written_files)
    assert all(path.suffix == '.md' for path in written_files)
    assert all(path.name.startswith('fragments_') for path in written_files)
    assert any('Apples are crisp' in path.read_text(encoding='utf-8') for path in written_files)
