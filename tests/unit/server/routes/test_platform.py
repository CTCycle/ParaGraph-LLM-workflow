from __future__ import annotations

from pathlib import Path
import shutil

from fastapi.testclient import TestClient
from sqlalchemy import Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ParaGraph.server.entities.nodecatalog import (
    HuggingFaceModelCatalogResponse,
    HuggingFaceModelDefinition,
    HuggingFaceModelDownloadCancelResponse,
    HuggingFaceModelDownloadResponse,
    HuggingFaceModelDownloadStatusResponse,
    OllamaLibraryCatalogResponse,
    OllamaLibraryModelDefinition,
    OllamaModelPullResponse,
    ProviderModelCatalogResponse,
    ProviderModelDefinition,
)
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
        'API_FETCHER',
        'BATCH_EMBEDDER',
        'CHUNKER',
        'CONTEXT_INJECTOR',
        'DATABASE_CONNECTION',
        'DATABASE_QUERY',
        'DOCUMENT_LOADER',
        'FIXED_SIZE_CHUNKS',
        'JSON_OUTPUT',
        'LLM_CHAT',
        'LLM_STRUCTURED',
        'LOAD_DOCUMENTS',
        'LOAD_TEXT',
        'MODEL_PROVIDER',
        'PROMPT',
        'SAVE_TEXT',
        'SIMILARITY_SEARCH',
        'SQL_DATABASE',
        'SQL_FILE_DATABASE',
        'TEMPLATE_FORMAT',
        'TEXT_CLEANER',
        'TEXT_OUTPUT',
        'VECTOR_DB_WRITER',
        'WEB_SCRAPER',
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
    staged_files = [Path(item) for item in payload['files']]
    try:
        assert payload['file_count'] == 2
        assert len(staged_files) == 2
        assert all(path.exists() for path in staged_files)
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


def test_nodes_upload_directory_rejects_absolute_paths(client: TestClient) -> None:
    response = client.post(
        '/nodes/uploads/directory',
        files=[('files', ('/etc/passwd', b'invalid', 'text/plain'))],
    )

    assert response.status_code == 422
    assert 'absolute paths' in response.json()['detail'].lower()



def test_nodes_database_connection_check_returns_success_for_sqlite(client: TestClient, tmp_path: Path) -> None:
    class TestHealthBase(DeclarativeBase):
        pass

    class TestTable(TestHealthBase):
        __tablename__ = 'test_table'
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        value: Mapped[str | None] = mapped_column(String, nullable=True)

    database_path = tmp_path / 'health.sqlite'
    engine = create_engine(f"sqlite:///{database_path}")
    TestHealthBase.metadata.create_all(engine)
    engine.dispose()

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

def test_huggingface_download_endpoint_returns_success(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        provider_service,
        'download_huggingface_model',
        lambda *, repo_id, session_name='default': HuggingFaceModelDownloadResponse(
            ok=True,
            repo_id=repo_id,
            message=f"Started download for Hugging Face model '{repo_id}'.",
            destination_path=f"ParaGraph/resources/models/huggingface/{repo_id.replace('/', '--')}",
            already_downloaded=False,
            job_id='job-1234',
            status='running',
            progress=0.0,
            downloaded_bytes=0,
            total_bytes=1024,
            poll_interval=1.0,
        ),
    )

    response = client.post('/providers/huggingface/download', json={'repo_id': 'meta-llama/Llama-3.2-3B-Instruct'})

    assert response.status_code == 200
    payload = response.json()
    assert payload['ok'] is True
    assert payload['repo_id'] == 'meta-llama/Llama-3.2-3B-Instruct'
    assert payload['job_id'] == 'job-1234'
    assert payload['status'] == 'running'


def test_huggingface_download_status_endpoint_returns_payload(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        provider_service,
        'get_huggingface_download_status',
        lambda *, job_id: HuggingFaceModelDownloadStatusResponse(
            job_id=job_id,
            repo_id='meta-llama/Llama-3.2-3B-Instruct',
            destination_path='ParaGraph/resources/models/huggingface/meta-llama--Llama-3.2-3B-Instruct',
            status='running',
            progress=42.0,
            message='Downloading files...',
            downloaded_bytes=420,
            total_bytes=1000,
            error=None,
        ),
    )

    response = client.get('/providers/huggingface/download/job-1234')

    assert response.status_code == 200
    payload = response.json()
    assert payload['job_id'] == 'job-1234'
    assert payload['status'] == 'running'
    assert payload['progress'] == 42.0


def test_huggingface_download_cancel_endpoint_returns_success(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        provider_service,
        'cancel_huggingface_download',
        lambda *, job_id: HuggingFaceModelDownloadCancelResponse(
            ok=True,
            job_id=job_id,
            repo_id='meta-llama/Llama-3.2-3B-Instruct',
            message='Cancellation requested.',
        ),
    )

    response = client.delete('/providers/huggingface/download/job-1234')

    assert response.status_code == 200
    payload = response.json()
    assert payload['ok'] is True
    assert payload['job_id'] == 'job-1234'

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

