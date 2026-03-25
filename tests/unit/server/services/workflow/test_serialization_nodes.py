from __future__ import annotations

from pathlib import Path

import pytest

from ParaGraph.server.services.workflow import node_registry


def test_save_and_load_text_supports_absolute_local_paths(tmp_path: Path) -> None:
    destination = tmp_path / 'exports' / 'saved'

    save_result = node_registry.execute(
        'SAVE_TEXT',
        1,
        {'output_path': str(destination), 'separate_files': False, 'extension': '.txt'},
        {'text': 'local file payload'},
    )

    expected_file = destination.with_suffix('.txt')
    assert expected_file.exists()
    assert expected_file.read_text(encoding='utf-8') == 'local file payload'
    assert save_result['artifact']['path'] == str(expected_file.resolve())

    loaded = node_registry.execute('LOAD_TEXT', 1, {'storage_path': str(expected_file)}, {})
    assert loaded['text'] == 'local file payload'


def test_save_text_supports_chunks_input_single_file_concat(tmp_path: Path) -> None:
    destination = tmp_path / 'exports' / 'chunks-output.md'

    save_result = node_registry.execute(
        'SAVE_TEXT',
        1,
        {'output_path': str(destination), 'separate_files': False, 'extension': '.md'},
        {
            'chunks': [
                {
                    'id': 'chunk-1',
                    'document_id': 'doc-1',
                    'text': 'First chunk body',
                    'source_uri': 'memory://doc-1',
                    'chunk_index': 0,
                    'token_count': 3,
                    'metadata': {},
                },
                {
                    'id': 'chunk-2',
                    'document_id': 'doc-1',
                    'text': 'Second chunk body',
                    'source_uri': 'memory://doc-1',
                    'chunk_index': 1,
                    'token_count': 3,
                    'metadata': {},
                },
            ]
        },
    )

    assert destination.exists()
    assert destination.read_text(encoding='utf-8') == 'First chunk body\n\nSecond chunk body'
    assert save_result['artifact']['count'] == 1
    assert save_result['artifact']['extension'] == '.md'


def test_save_text_supports_documents_input_with_separate_files(tmp_path: Path) -> None:
    destination_folder = tmp_path / 'exports' / 'documents'

    save_result = node_registry.execute(
        'SAVE_TEXT',
        1,
        {'output_path': str(destination_folder), 'separate_files': True, 'extension': '.txt'},
        {
            'documents': [
                {
                    'id': 'doc-1',
                    'text': 'alpha',
                    'source_uri': 'memory://alpha',
                    'mime_type': 'text/plain',
                    'metadata': {'file_name': 'alpha.txt'},
                },
                {
                    'id': 'doc-2',
                    'text': 'beta',
                    'source_uri': 'memory://beta',
                    'mime_type': 'text/plain',
                    'metadata': {'file_name': 'beta.txt'},
                },
            ]
        },
    )

    artifact = save_result['artifact']
    assert artifact['separate_files'] is True
    assert artifact['count'] == 2
    saved_paths = [Path(path) for path in artifact['files']]
    assert all(path.exists() for path in saved_paths)
    assert sorted(path.read_text(encoding='utf-8') for path in saved_paths) == ['alpha', 'beta']


def test_load_text_rejects_empty_storage_path() -> None:
    with pytest.raises(ValueError, match='storage_path is required'):
        node_registry.execute('LOAD_TEXT', 1, {'storage_path': ''}, {})


def test_save_text_rejects_relative_path_traversal() -> None:
    with pytest.raises(ValueError, match='must resolve inside'):
        node_registry.execute(
            'SAVE_TEXT',
            1,
            {'output_path': '../../outside.txt', 'separate_files': False, 'extension': '.txt'},
            {'text': 'payload'},
        )


def test_save_text_rejects_absolute_paths_in_cloud_mode(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv('PARAGRAPH_DEPLOYMENT_MODE', 'cloud')
    destination = tmp_path / 'exports' / 'saved.txt'
    with pytest.raises(ValueError, match='must resolve inside'):
        node_registry.execute(
            'SAVE_TEXT',
            1,
            {'output_path': str(destination), 'separate_files': False, 'extension': '.txt'},
            {'text': 'cloud payload'},
        )
