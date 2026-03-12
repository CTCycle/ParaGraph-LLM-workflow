from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from ParaGraph.server.services.workflow import node_registry
from ParaGraph.server.services.workflow import nodes as node_module


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


def test_rag_nodes_roundtrip_from_document_to_context(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(node_module.provider_service, 'embed_text', fake_embed)

    source = tmp_path / 'produce.txt'
    source.write_text('Apples are crisp. Apples pair well with cinnamon. Bananas are softer.', encoding='utf-8')
    index_name = f'test-rag-{uuid4().hex[:8]}'

    try:
        documents = node_registry.execute('DOCUMENT_LOADER', 1, {'file_path': str(source)}, {})
        cleaned = node_registry.execute(
            'TEXT_CLEANER',
            1,
            {'strip_html_content': True, 'collapse_whitespace': True},
            {'documents': documents['documents']},
        )
        chunks = node_registry.execute(
            'CHUNKER',
            1,
            {
                'strategy': 'token',
                'chunk_size_tokens': 100,
                'chunk_overlap_tokens': 20,
                'respect_sentence_boundaries': True,
            },
            {'documents': cleaned['documents']},
        )
        points = node_registry.execute(
            'BATCH_EMBEDDER',
            1,
            {
                'provider': 'ollama',
                'model_name': 'nomic-embed-text',
                'batch_size': 4,
                'dimensions': 3,
                'normalize': True,
                'max_retries': 0,
            },
            {'chunks': chunks['chunks']},
        )
        store = node_registry.execute(
            'VECTOR_DB_WRITER',
            1,
            {
                'backend': 'faiss',
                'index_name': index_name,
                'metric': 'cosine',
                'index_type': 'flat',
                'write_mode': 'overwrite',
                'nlist': 8,
                'hnsw_m': 16,
            },
            {'points': points['points']},
        )
        results = node_registry.execute(
            'SIMILARITY_SEARCH',
            1,
            {'top_k': 2, 'score_threshold': 0, 'filter': {}, 'include_metadata': True},
            {'query': 'apples', 'store': store['store']},
        )
        context = node_registry.execute(
            'CONTEXT_INJECTOR',
            1,
            {'max_context_items': 2, 'include_citations': True, 'separator': '\n\n'},
            {'results': results['results']},
        )

        assert len(chunks['chunks']) >= 1
        assert results['results']['hits']
        assert 'Apples' in results['results']['hits'][0]['text']
        assert '[1]' in context['text']
        assert 'Apples are crisp' in context['text']
    finally:
        store_path = Path('ParaGraph/resources/artifacts/vectorstores') / index_name
        if store_path.exists():
            shutil.rmtree(store_path)
