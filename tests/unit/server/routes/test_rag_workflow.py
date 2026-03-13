from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from ParaGraph.server.entities.nodecatalog import ProviderModelDefinition
from ParaGraph.server.services.workflow import nodes as node_module


def build_stub_model_definition(provider: str, model: str) -> ProviderModelDefinition:
    return ProviderModelDefinition(
        provider=provider,
        model=model,
        label=model,
        supports_image=False,
        supports_reasoning=True,
        supports_structured_output=True,
    )


def fake_embed(provider: str, model: str, text: str, dimensions: int | None = None, session_name: str = 'default') -> list[float]:
    _ = provider
    _ = model
    _ = session_name
    lower = text.lower()
    vector = [
        float(lower.count('apples')),
        float(lower.count('bananas')),
        float(lower.count('carrots')),
    ]
    if dimensions is not None:
        vector = (vector + [0.0] * dimensions)[:dimensions]
    return vector


def build_rag_definition(source_path: str, index_name: str) -> dict[str, object]:
    return {
        'schema_version': 2,
        'nodes': [
            {'node_id': 'doc_1', 'node_type': 'DOCUMENT_LOADER', 'node_version': 1, 'parameters': {'file_path': source_path}},
            {'node_id': 'clean_1', 'node_type': 'TEXT_CLEANER', 'node_version': 1, 'parameters': {'strip_html_content': True, 'collapse_whitespace': True}},
            {'node_id': 'chunk_1', 'node_type': 'CHUNKER', 'node_version': 1, 'parameters': {'strategy': 'token', 'chunk_size_tokens': 100, 'chunk_overlap_tokens': 20, 'respect_sentence_boundaries': True}},
            {'node_id': 'embed_1', 'node_type': 'BATCH_EMBEDDER', 'node_version': 1, 'parameters': {'provider': 'ollama', 'model_name': 'nomic-embed-text', 'batch_size': 4, 'dimensions': 3, 'normalize': True, 'max_retries': 0}},
            {'node_id': 'store_1', 'node_type': 'VECTOR_DB_WRITER', 'node_version': 1, 'parameters': {'backend': 'faiss', 'index_name': index_name, 'metric': 'cosine', 'index_type': 'flat', 'write_mode': 'overwrite', 'nlist': 8, 'hnsw_m': 16}},
            {'node_id': 'query_1', 'node_type': 'USER_PROMPT', 'node_version': 1, 'parameters': {'prompt_text': 'apples'}},
            {'node_id': 'search_1', 'node_type': 'SIMILARITY_SEARCH', 'node_version': 1, 'parameters': {'top_k': 2, 'score_threshold': 0, 'filter': {}, 'include_metadata': True}},
            {'node_id': 'context_1', 'node_type': 'CONTEXT_INJECTOR', 'node_version': 1, 'parameters': {'max_context_items': 2, 'include_citations': True, 'separator': '\n\n'}},
            {'node_id': 'template_1', 'node_type': 'TEMPLATE_FORMAT', 'node_version': 1, 'parameters': {'template': 'Use this context to answer the question:\n{input}'}},
            {'node_id': 'provider_1', 'node_type': 'MODEL_PROVIDER', 'node_version': 1, 'parameters': {'provider': 'ollama', 'model_name': 'llama3.2'}},
            {'node_id': 'chat_1', 'node_type': 'LLM_CHAT', 'node_version': 1, 'parameters': {'context_window': 0, 'max_tokens': 64, 'use_reasoning': False}},
            {'node_id': 'output_1', 'node_type': 'TEXT_OUTPUT', 'node_version': 1, 'parameters': {}},
        ],
        'connections': [
            {'from_node': 'doc_1', 'from_output': 'documents', 'to_node': 'clean_1', 'to_input': 'documents'},
            {'from_node': 'clean_1', 'from_output': 'documents', 'to_node': 'chunk_1', 'to_input': 'documents'},
            {'from_node': 'chunk_1', 'from_output': 'chunks', 'to_node': 'embed_1', 'to_input': 'chunks'},
            {'from_node': 'embed_1', 'from_output': 'points', 'to_node': 'store_1', 'to_input': 'points'},
            {'from_node': 'query_1', 'from_output': 'text', 'to_node': 'search_1', 'to_input': 'query'},
            {'from_node': 'store_1', 'from_output': 'store', 'to_node': 'search_1', 'to_input': 'store'},
            {'from_node': 'search_1', 'from_output': 'results', 'to_node': 'context_1', 'to_input': 'results'},
            {'from_node': 'context_1', 'from_output': 'text', 'to_node': 'template_1', 'to_input': 'input'},
            {'from_node': 'template_1', 'from_output': 'text', 'to_node': 'chat_1', 'to_input': 'user_prompt'},
            {'from_node': 'provider_1', 'connection_type': 'controller', 'from_controller': 'model', 'to_node': 'chat_1', 'to_controller': 'model'},
            {'from_node': 'chat_1', 'from_output': 'response', 'to_node': 'output_1', 'to_input': 'text'},
        ],
        'metadata': {},
    }


def test_execute_rag_pipeline_returns_text_output(
    client: TestClient,
    monkeypatch,
    tmp_path: Path,
    wait_for_job,
) -> None:
    source = tmp_path / 'rag-source.txt'
    source.write_text('Apples are crisp and sweet. Bananas are softer and milder.', encoding='utf-8')
    index_name = f'test-rag-run-{uuid4().hex[:8]}'

    monkeypatch.setattr(node_module.provider_service, 'embed_text', fake_embed)
    monkeypatch.setattr(node_module.provider_service, 'validate_model_request', lambda **kwargs: None)
    monkeypatch.setattr(node_module.provider_service, 'get_model_metadata', lambda provider, model, session_name='default': build_stub_model_definition(provider, model))
    monkeypatch.setattr(node_module.provider_service, 'build_model_definition', lambda provider, model, session_name='default': build_stub_model_definition(provider, model))
    monkeypatch.setattr(node_module.provider_service, 'chat', lambda **kwargs: 'Apples are the most relevant result.')

    try:
        compile_response = client.post('/executions/compile', json={'definition': build_rag_definition(str(source), index_name)})
        assert compile_response.status_code == 200
        payload = compile_response.json()
        assert payload['valid'] is True

        start_response = client.post('/executions', json={'workflow_id': None, 'plan': payload['plan']})
        assert start_response.status_code == 202
        run_id = start_response.json()['run_id']

        final_status = wait_for_job(str(run_id), 3.0)
        run_payload = client.get(f'/executions/{run_id}').json()

        assert final_status['status'] == 'completed'
        assert run_payload['outputs'] == {'output_1': {'text': 'Apples are the most relevant result.'}}
        context_step = next(step for step in run_payload['steps'] if step['node_id'] == 'context_1')
        assert 'Apples are crisp and sweet.' in context_step['output']['ports']['text']
    finally:
        store_path = Path('ParaGraph/resources/artifacts/vectorstores') / index_name
        if store_path.exists():
            shutil.rmtree(store_path)

