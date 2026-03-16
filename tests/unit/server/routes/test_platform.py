from __future__ import annotations

from pathlib import Path
import shutil
import sqlite3

from fastapi.testclient import TestClient

from ParaGraph.server.entities.nodecatalog import (
    HuggingFaceModelCatalogResponse,
    HuggingFaceModelDefinition,
    OllamaLibraryCatalogResponse,
    OllamaLibraryModelDefinition,
    OllamaModelPullResponse,
    ProviderModelCatalogResponse,
    ProviderModelDefinition,
)
from ParaGraph.server.routes import nodes as node_routes
from ParaGraph.server.services.workflow import nodes as node_module
from ParaGraph.server.services.workflow import provider_service


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
    assert ids == {
        'PROMPT',
        'WEB_SCRAPER',
        'MODEL_PROVIDER',
        'LLM_CHAT',
        'LLM_STRUCTURED',
        'SQL_DATABASE',
        'SQL_FILE_DATABASE',
        'FIXED_SIZE_CHUNKS',
        'TEXT_OUTPUT',
        'JSON_OUTPUT',
        'LOAD_DOCUMENTS',
    }
    assert 'USER_PROMPT' not in ids
    assert 'SYSTEM_PROMPT' not in ids
    assert 'LLM_GENERATE' not in ids


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


def test_nodes_dialog_files_returns_selected_paths(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(node_routes, 'pick_files', lambda multiple: ['C:/tmp/a.txt', 'C:/tmp/b.txt'] if multiple else ['C:/tmp/a.txt'])

    response = client.get('/nodes/dialog/files?multiple=true')

    assert response.status_code == 200
    assert response.json() == {'paths': ['C:/tmp/a.txt', 'C:/tmp/b.txt']}


def test_nodes_dialog_directory_returns_selected_path(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(node_routes, 'pick_directory', lambda: 'C:/tmp/data')

    response = client.get('/nodes/dialog/directory')

    assert response.status_code == 200
    assert response.json() == {'path': 'C:/tmp/data'}


def test_nodes_upload_directory_stages_browser_selected_folder(client: TestClient) -> None:
    response = client.post(
        '/nodes/uploads/directory',
        files=[
            ('files', ('dataset/readme.txt', b'hello world', 'text/plain')),
            ('files', ('dataset/nested/notes.md', b'# Notes', 'text/markdown')),
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    staged_root = Path(payload['path'])
    try:
        assert payload['file_count'] == 2
        assert (staged_root / 'dataset' / 'readme.txt').read_text(encoding='utf-8') == 'hello world'
        assert (staged_root / 'dataset' / 'nested' / 'notes.md').read_text(encoding='utf-8') == '# Notes'
    finally:
        if staged_root.exists():
            shutil.rmtree(staged_root, ignore_errors=True)


def test_nodes_upload_directory_rejects_parent_directory_segments(client: TestClient) -> None:
    response = client.post(
        '/nodes/uploads/directory',
        files=[('files', ('../escape.txt', b'invalid', 'text/plain'))],
    )

    assert response.status_code == 422
    assert 'relative paths' in response.json()['detail'].lower()



def test_nodes_database_connection_check_returns_success_for_sqlite(client: TestClient, tmp_path: Path) -> None:
    database_path = tmp_path / 'health.sqlite'
    with sqlite3.connect(database_path) as connection:
        connection.execute('CREATE TABLE test_table (id INTEGER PRIMARY KEY, value TEXT)')
        connection.commit()

    response = client.post(
        '/nodes/check-database-connection',
        json={
            'node_type': 'SQL_FILE_DATABASE',
            'node_version': 1,
            'parameters': {
                'db_engine': 'sqlite',
                'db_path': str(database_path),
                'db_name': 'health',
                'db_user': 'postgres',
                'db_password': 'change_me',
                'db_ssl': False,
                'db_ssl_ca': '',
                'db_connect_timeout': 5,
            },
        },
    )

    assert response.status_code == 200
    assert response.json() == {'ok': True, 'message': 'Database connection successful.'}


def test_nodes_database_connection_check_returns_failure_payload(client: TestClient) -> None:
    response = client.post(
        '/nodes/check-database-connection',
        json={
            'node_type': 'SQL_FILE_DATABASE',
            'node_version': 1,
            'parameters': {
                'db_engine': 'sqlite',
                'db_path': 'C:/does/not/exist/missing.sqlite',
                'db_name': 'missing',
                'db_user': 'postgres',
                'db_password': 'change_me',
                'db_ssl': False,
                'db_ssl_ca': '',
                'db_connect_timeout': 5,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['ok'] is False
    assert 'not found' in payload['message'].lower()

def test_provider_models_endpoint_returns_catalog(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        provider_service,
        'list_models',
        lambda session_name='default': ProviderModelCatalogResponse(
            models=[
                ProviderModelDefinition(
                    provider='ollama',
                    model='llama3.2',
                    label='Llama 3.2',
                    supports_image=False,
                    supports_reasoning=False,
                    supports_structured_output=True,
                )
            ]
        ),
    )

    response = client.get('/providers/models')

    assert response.status_code == 200
    assert response.json()['models'][0]['model'] == 'llama3.2'


def test_ollama_library_endpoint_returns_rows(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        provider_service,
        'list_ollama_library_models',
        lambda **kwargs: OllamaLibraryCatalogResponse(
            models=[
                OllamaLibraryModelDefinition(
                    model='llama3.2',
                    description='Llama model',
                    homepage='https://ollama.com/library/llama3.2',
                    pulled=True,
                )
            ],
            total_count=1,
            pulled_count=1,
            refreshed_at='2026-03-16T00:00:00+00:00',
            source='https://ollama.com/library',
        ),
    )

    response = client.get('/providers/ollama/library?refresh=true')

    assert response.status_code == 200
    payload = response.json()
    assert payload['models'][0]['model'] == 'llama3.2'
    assert payload['models'][0]['pulled'] is True


def test_ollama_pull_endpoint_returns_success(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        provider_service,
        'pull_ollama_model',
        lambda *, model, session_name='default': OllamaModelPullResponse(
            ok=True,
            model=model,
            message=f"Model '{model}' is available in Ollama.",
        ),
    )

    response = client.post('/providers/ollama/pull', json={'model': 'llama3.2'})

    assert response.status_code == 200
    payload = response.json()
    assert payload['ok'] is True
    assert payload['model'] == 'llama3.2'


def test_huggingface_models_endpoint_returns_rows(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        provider_service,
        'list_huggingface_models',
        lambda **kwargs: HuggingFaceModelCatalogResponse(
            models=[
                HuggingFaceModelDefinition(
                    repo_id='meta-llama/Llama-3.2-3B-Instruct',
                    author='meta-llama',
                    task='text-generation',
                    library='transformers',
                    likes=10,
                    downloads=100,
                    visibility='public',
                    private=False,
                    gated=False,
                    last_modified='2026-03-16T00:00:00+00:00',
                    url='https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct',
                )
            ],
            page=1,
            page_size=25,
            has_more=True,
            using_token=False,
            warning=None,
        ),
    )

    response = client.get('/providers/huggingface/models?search=llama&sort=downloads&page=1&page_size=25')

    assert response.status_code == 200
    payload = response.json()
    assert payload['models'][0]['repo_id'] == 'meta-llama/Llama-3.2-3B-Instruct'
    assert payload['has_more'] is True

def test_compile_endpoint_returns_diagnostics_for_type_mismatch(client: TestClient) -> None:
    response = client.post(
        '/executions/compile',
        json={
            'definition': {
                'schema_version': 2,
                'nodes': [
                    {'node_id': 'web_1', 'node_type': 'WEB_SCRAPER', 'node_version': 1, 'parameters': {'url': 'https://example.com'}},
                    {'node_id': 'output_1', 'node_type': 'TEXT_OUTPUT', 'node_version': 1, 'parameters': {}},
                ],
                'connections': [
                    {'from_node': 'web_1', 'from_output': 'documents', 'to_node': 'output_1', 'to_input': 'text'},
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
