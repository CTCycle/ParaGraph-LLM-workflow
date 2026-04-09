from __future__ import annotations

from pathlib import Path

import pytest

from ParaGraph.server.configurations.server import reload_settings_for_tests
from ParaGraph.server.services.workflow import node_registry
from ParaGraph.server.services.workflow.node_handlers import core as core_node_handlers


@pytest.fixture(autouse=True)
def reset_settings_cache() -> None:
    reload_settings_for_tests()
    yield
    reload_settings_for_tests()



def test_save_as_file_and_load_text_supports_absolute_local_paths(tmp_path: Path) -> None:
    destination = tmp_path / 'exports' / 'saved'

    save_result = node_registry.execute(
        'SAVE_AS_FILE',
        1,
        {'output_path': str(destination), 'extension': '.txt'},
        {'text': 'local file payload'},
    )

    expected_file = destination.with_suffix('.txt')
    assert expected_file.exists()
    assert expected_file.read_text(encoding='utf-8') == 'local file payload'
    assert save_result['artifact']['path'] == str(expected_file.resolve())

    loaded = node_registry.execute('LOAD_TEXT', 1, {'storage_path': str(expected_file)}, {})
    assert loaded['text'] == 'local file payload'



def test_load_text_supports_workspace_relative_paths(tmp_path: Path, monkeypatch) -> None:
    source_file = tmp_path / 'relative-source.txt'
    source_file.write_text('relative payload', encoding='utf-8')

    monkeypatch.chdir(tmp_path)
    loaded = node_registry.execute('LOAD_TEXT', 1, {'storage_path': source_file.name}, {})

    assert loaded['text'] == 'relative payload'



def test_load_text_rejects_non_canonical_storage_path_keys(tmp_path: Path) -> None:
    source_file = tmp_path / 'legacy-source.txt'
    source_file.write_text('legacy payload', encoding='utf-8')

    invalid_payloads = [
        {'storagePath': str(source_file)},
        {'storage path': str(source_file)},
        {'file_path': str(source_file)},
        {'path': str(source_file)},
    ]

    for payload in invalid_payloads:
        with pytest.raises(ValueError, match='storage_path is required'):
            node_registry.execute('LOAD_TEXT', 1, payload, {})



def test_save_as_file_supports_chunks_input_single_file_concat(tmp_path: Path) -> None:
    destination = tmp_path / 'exports' / 'chunks-output.md'

    save_result = node_registry.execute(
        'SAVE_AS_FILE',
        1,
        {'output_path': str(destination), 'extension': '.md'},
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
    assert destination.read_text(encoding='utf-8') == 'First chunk body/n/nSecond chunk body'
    assert save_result['artifact']['count'] == 1
    assert save_result['artifact']['extension'] == '.md'



def test_save_as_file_overwrites_existing_single_file_output(tmp_path: Path) -> None:
    destination = tmp_path / 'exports' / 'existing.txt'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text('stale payload', encoding='utf-8')

    save_result = node_registry.execute(
        'SAVE_AS_FILE',
        1,
        {'output_path': str(destination), 'extension': '.txt'},
        {'text': 'fresh payload'},
    )

    assert destination.read_text(encoding='utf-8') == 'fresh payload'
    assert save_result['artifact']['path'] == str(destination.resolve())
    assert save_result['artifact']['files'] == [str(destination.resolve())]



def test_save_as_file_uses_file_name_from_output_path_without_extension(tmp_path: Path) -> None:
    destination = tmp_path / 'exports' / 'file_name'

    save_result = node_registry.execute(
        'SAVE_AS_FILE',
        1,
        {'output_path': str(destination), 'extension': '.txt'},
        {'text': 'payload'},
    )

    expected_file = destination.with_suffix('.txt')
    assert expected_file.exists()
    assert expected_file.read_text(encoding='utf-8') == 'payload'
    assert save_result['artifact']['path'] == str(expected_file.resolve())



def test_save_as_folder_supports_documents_input_with_multiple_files(tmp_path: Path) -> None:
    destination_folder = tmp_path / 'exports' / 'documents'

    save_result = node_registry.execute(
        'SAVE_AS_FOLDER',
        1,
        {'output_path': str(destination_folder), 'extension': '.txt'},
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
    saved_paths = [Path(path) for path in artifact['files']]
    assert artifact['count'] == 2
    assert artifact['path'] == str(destination_folder.resolve())
    assert destination_folder.exists() and destination_folder.is_dir()
    assert all(path.exists() for path in saved_paths)
    assert all(path.parent == destination_folder for path in saved_paths)
    assert [path.name for path in saved_paths] == ['documents_000001.txt', 'documents_000002.txt']
    assert [path.read_text(encoding='utf-8') for path in saved_paths] == ['alpha', 'beta']



def test_save_as_folder_writes_single_text_as_single_file(tmp_path: Path) -> None:
    destination_folder = tmp_path / 'exports' / 'single_text'

    save_result = node_registry.execute(
        'SAVE_AS_FOLDER',
        1,
        {'output_path': str(destination_folder), 'extension': '.txt'},
        {'text': 'payload'},
    )

    saved_paths = [Path(path) for path in save_result['artifact']['files']]
    assert save_result['artifact']['count'] == 1
    assert destination_folder.exists() and destination_folder.is_dir()
    assert len(saved_paths) == 1
    assert saved_paths[0].name == 'single_text_000001.txt'
    assert saved_paths[0].read_text(encoding='utf-8') == 'payload'



def test_save_as_folder_replaces_file_collision_with_folder(tmp_path: Path) -> None:
    destination_folder = tmp_path / 'exports' / 'batch'
    destination_folder.parent.mkdir(parents=True, exist_ok=True)
    destination_folder.write_text('legacy single file', encoding='utf-8')

    save_result = node_registry.execute(
        'SAVE_AS_FOLDER',
        1,
        {'output_path': str(destination_folder), 'extension': '.txt'},
        {
            'documents': [
                {
                    'id': 'doc-1',
                    'text': 'alpha',
                    'source_uri': 'memory://alpha',
                    'mime_type': 'text/plain',
                    'metadata': {},
                },
                {
                    'id': 'doc-2',
                    'text': 'beta',
                    'source_uri': 'memory://beta',
                    'mime_type': 'text/plain',
                    'metadata': {},
                },
            ]
        },
    )

    assert destination_folder.exists() and destination_folder.is_dir()
    saved_paths = [Path(path) for path in save_result['artifact']['files']]
    assert all(path.parent == destination_folder for path in saved_paths)
    assert [path.read_text(encoding='utf-8') for path in saved_paths] == ['alpha', 'beta']



def test_save_as_file_client_side_write_returns_metadata_without_backend_write(tmp_path: Path) -> None:
    destination = tmp_path / 'desktop' / 'file_name'

    save_result = node_registry.execute(
        'SAVE_AS_FILE',
        1,
        {
            'output_path': str(destination),
            'extension': '.txt',
            'client_side_write': True,
        },
        {'text': 'payload'},
    )

    expected_file = destination.with_suffix('.txt')
    assert not expected_file.exists()
    assert save_result['artifact']['path'] == str(expected_file)
    assert save_result['artifact']['files'] == [str(expected_file)]
    assert save_result['artifact']['item_texts'] == ['payload']



def test_save_as_folder_client_side_write_returns_metadata_without_backend_write(tmp_path: Path) -> None:
    destination = tmp_path / 'desktop' / 'batch'

    save_result = node_registry.execute(
        'SAVE_AS_FOLDER',
        1,
        {
            'output_path': str(destination),
            'extension': '.txt',
            'client_side_write': True,
        },
        {
            'chunks': [
                {
                    'id': 'chunk-1',
                    'document_id': 'doc-1',
                    'text': 'alpha',
                    'source_uri': 'memory://doc-1',
                    'chunk_index': 0,
                    'token_count': 1,
                    'metadata': {},
                },
                {
                    'id': 'chunk-2',
                    'document_id': 'doc-1',
                    'text': 'beta',
                    'source_uri': 'memory://doc-1',
                    'chunk_index': 1,
                    'token_count': 1,
                    'metadata': {},
                },
            ]
        },
    )

    expected_files = [
        destination / 'batch_000001.txt',
        destination / 'batch_000002.txt',
    ]

    assert not destination.exists()
    assert save_result['artifact']['path'] == str(destination)
    assert save_result['artifact']['files'] == [str(path) for path in expected_files]
    assert save_result['artifact']['item_texts'] == ['alpha', 'beta']



def test_save_as_file_client_side_write_resolves_deferred_documents_into_item_texts(tmp_path: Path) -> None:
    source_file = tmp_path / 'source.txt'
    source_file.write_text('resolved deferred document', encoding='utf-8')

    destination = tmp_path / 'desktop' / 'from-load-documents.txt'
    save_result = node_registry.execute(
        'SAVE_AS_FILE',
        1,
        {
            'output_path': str(destination),
            'extension': '.txt',
            'client_side_write': True,
        },
        {
            'documents': [
                {
                    'id': 'doc-1',
                    'text': '',
                    'source_uri': str(source_file),
                    'mime_type': 'text/plain',
                    'metadata': {
                        'deferred_load': True,
                        'file_name': source_file.name,
                        'file_path': str(source_file),
                    },
                }
            ]
        },
    )

    expected_file = destination.with_suffix('.txt')
    assert not expected_file.exists()
    assert save_result['artifact']['path'] == str(expected_file)
    assert save_result['artifact']['files'] == [str(expected_file)]
    assert save_result['artifact']['item_texts'] == ['resolved deferred document']



def test_load_text_rejects_empty_storage_path() -> None:
    with pytest.raises(ValueError, match='storage_path is required'):
        node_registry.execute('LOAD_TEXT', 1, {'storage_path': ''}, {})



def test_save_as_file_rejects_relative_path_traversal() -> None:
    with pytest.raises(ValueError, match='must resolve inside'):
        node_registry.execute(
            'SAVE_AS_FILE',
            1,
            {'output_path': '../../outside.txt', 'extension': '.txt'},
            {'text': 'payload'},
        )



def test_save_as_folder_rejects_relative_path_traversal() -> None:
    with pytest.raises(ValueError, match='must resolve inside'):
        node_registry.execute(
            'SAVE_AS_FOLDER',
            1,
            {'output_path': '../../outside', 'extension': '.txt'},
            {'text': 'payload'},
        )



def test_save_as_file_rejects_absolute_paths_in_cloud_mode(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv('PARAGRAPH_CLOUD_MODE', 'true')
    reload_settings_for_tests()
    destination = tmp_path / 'exports' / 'saved.txt'
    with pytest.raises(ValueError, match='must resolve inside'):
        node_registry.execute(
            'SAVE_AS_FILE',
            1,
            {'output_path': str(destination), 'extension': '.txt'},
            {'text': 'cloud payload'},
        )



def test_save_as_folder_rejects_absolute_paths_in_cloud_mode(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv('PARAGRAPH_CLOUD_MODE', 'true')
    reload_settings_for_tests()
    destination = tmp_path / 'exports' / 'saved'
    with pytest.raises(ValueError, match='must resolve inside'):
        node_registry.execute(
            'SAVE_AS_FOLDER',
            1,
            {'output_path': str(destination), 'extension': '.txt'},
            {'text': 'cloud payload'},
        )


def test_load_text_supports_non_utf8_text_with_fallback_encoding(tmp_path: Path) -> None:
    source_file = tmp_path / 'latin1.txt'
    source_file.write_bytes('café in latin1'.encode('latin-1'))

    loaded = node_registry.execute('LOAD_TEXT', 1, {'storage_path': str(source_file)}, {})

    assert loaded['text'] == 'café in latin1'


def test_load_text_uses_shared_loader_for_pdf_paths(monkeypatch, tmp_path: Path) -> None:
    source_file = tmp_path / 'sample.pdf'
    source_file.write_bytes(b'%PDF-1.4\n%%EOF\n')

    observed: dict[str, Path] = {}

    def fake_loader(path: Path) -> tuple[str, str]:
        observed['path'] = path
        return ('pdf payload', 'application/pdf')

    monkeypatch.setattr(core_node_handlers, 'load_file_text', fake_loader)

    loaded = node_registry.execute('LOAD_TEXT', 1, {'storage_path': str(source_file)}, {})

    assert loaded['text'] == 'pdf payload'
    assert observed['path'] == source_file.resolve()


def test_save_as_folder_resolves_deferred_documents_before_writing(tmp_path: Path) -> None:
    source_file = tmp_path / 'deferred.txt'
    source_file.write_text('resolved deferred text', encoding='utf-8')

    destination_folder = tmp_path / 'exports' / 'resolved_docs'
    result = node_registry.execute(
        'SAVE_AS_FOLDER',
        1,
        {'output_path': str(destination_folder), 'extension': '.txt'},
        {
            'documents': [
                {
                    'id': 'doc-1',
                    'text': '',
                    'source_uri': str(source_file),
                    'mime_type': 'text/plain',
                    'metadata': {
                        'deferred_load': True,
                        'file_name': source_file.name,
                        'file_path': str(source_file),
                    },
                }
            ]
        },
    )

    saved_paths = [Path(path) for path in result['artifact']['files']]
    assert len(saved_paths) == 1
    assert saved_paths[0].read_text(encoding='utf-8') == 'resolved deferred text'
