from __future__ import annotations

from pathlib import Path

import pytest

from ParaGraph.server.services.workflow import node_registry
from ParaGraph.server.services.workflow import nodes as node_module


def test_save_and_load_text_supports_absolute_local_paths(tmp_path: Path) -> None:
    destination = tmp_path / 'exports' / 'saved.txt'

    save_result = node_registry.execute(
        'SAVE_TEXT',
        1,
        {'storage_path': str(destination)},
        {'text': 'local file payload'},
    )

    assert destination.exists()
    assert destination.read_text(encoding='utf-8') == 'local file payload'
    assert save_result['artifact']['path'] == str(destination)

    loaded = node_registry.execute('LOAD_TEXT', 1, {'storage_path': str(destination)}, {})
    assert loaded['text'] == 'local file payload'


def test_load_text_rejects_empty_storage_path() -> None:
    with pytest.raises(ValueError, match='storage_path is required'):
        node_registry.execute('LOAD_TEXT', 1, {'storage_path': ''}, {})


def test_vector_db_writer_uses_selected_storage_directory(monkeypatch, tmp_path: Path) -> None:
    index_name = 'custom-store'
    storage_directory = tmp_path / 'vector-root'
    points = [
        {
            'id': 'p1',
            'chunk_id': 'c1',
            'document_id': 'd1',
            'text': 'apples are crisp',
            'source_uri': 'memory://doc',
            'vector': [1.0, 0.0, 0.0],
            'embedding_provider': 'ollama',
            'embedding_model': 'nomic-embed-text',
            'metadata': {},
        }
    ]

    monkeypatch.setattr(
        node_module.provider_service,
        'embed_text',
        lambda provider, model, text, dimensions=None, session_name='default': [1.0, 0.0, 0.0],
    )

    store_result = node_registry.execute(
        'VECTOR_DB_WRITER',
        1,
        {
            'backend': 'faiss',
            'index_name': index_name,
            'storage_directory': str(storage_directory),
            'metric': 'cosine',
            'index_type': 'flat',
            'write_mode': 'overwrite',
            'nlist': 8,
            'hnsw_m': 16,
        },
        {'points': points},
    )

    expected_store_path = (storage_directory / index_name).resolve()
    store_handle = store_result['store']
    assert Path(store_handle['artifact_path']) == expected_store_path
    assert store_handle['metadata']['storage_directory'] == str(storage_directory.resolve())

    results = node_registry.execute(
        'SIMILARITY_SEARCH',
        1,
        {'top_k': 1, 'score_threshold': 0, 'filter': {}, 'include_metadata': True},
        {'query': 'apples', 'store': store_handle},
    )

    assert len(results['results']['hits']) == 1
    assert results['results']['hits'][0]['id'] == 'p1'
