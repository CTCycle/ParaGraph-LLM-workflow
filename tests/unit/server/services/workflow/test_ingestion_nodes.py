from __future__ import annotations

import sqlite3
from pathlib import Path

from ParaGraph.server.services.workflow import node_registry
from ParaGraph.server.services.workflow.node_handlers import ingestion as ingestion_module


class FakeApiResponse:
    def __init__(self, url: str, payload: dict[str, object]) -> None:
        self.url = url
        self._payload = payload
        self.status_code = 200
        self.headers = {'content-type': 'application/json'}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload

    @property
    def text(self) -> str:
        return ''


def test_document_loader_accepts_multiple_files(tmp_path: Path) -> None:
    source_a = tmp_path / 'one.txt'
    source_b = tmp_path / 'two.md'
    source_a.write_text('alpha', encoding='utf-8')
    source_b.write_text('beta', encoding='utf-8')

    payload = node_registry.execute('DOCUMENT_LOADER', 1, {'file_paths': [str(source_a), str(source_b)]}, {})

    assert [document['text'] for document in payload['documents']] == ['alpha', 'beta']
    assert all(document['source_uri'].startswith(str(tmp_path)) for document in payload['documents'])


def test_api_fetcher_caps_request_list_and_extracts_selected_json(monkeypatch) -> None:
    responses = {
        'https://api.test/first': {'payload': {'text': 'first'}},
        'https://api.test/second': {'payload': {'text': 'second'}},
    }

    def fake_get(url: str, timeout: float, follow_redirects: bool, headers: dict[str, str]):
        _ = timeout
        _ = follow_redirects
        _ = headers
        return FakeApiResponse(url, responses[url])

    monkeypatch.setattr(ingestion_module.httpx, 'get', fake_get)

    payload = node_registry.execute(
        'API_FETCHER',
        1,
        {
            'url': 'https://api.test/first',
            'request_urls': ['https://api.test/first', 'https://api.test/second'],
            'response_selector': 'payload.text',
            'max_calls': 2,
            'allow_concurrency': False,
        },
        {},
    )

    assert [document['text'] for document in payload['documents']] == ['first', 'second']
    assert payload['documents'][1]['metadata']['call_index'] == 1


def test_database_connection_and_query_roundtrip(tmp_path: Path) -> None:
    database_path = tmp_path / 'records.sqlite'
    with sqlite3.connect(database_path) as connection:
        connection.execute('CREATE TABLE notes (id INTEGER PRIMARY KEY, title TEXT, body TEXT)')
        connection.execute('INSERT INTO notes (title, body) VALUES (?, ?)', ('Alpha', 'First row'))
        connection.execute('INSERT INTO notes (title, body) VALUES (?, ?)', ('Beta', 'Second row'))
        connection.commit()

    connection_payload = node_registry.execute(
        'DATABASE_CONNECTION',
        1,
        {'engine': 'sqlite', 'file_path': str(database_path), 'connect_timeout_s': 5},
        {},
    )
    query_payload = node_registry.execute(
        'DATABASE_QUERY',
        1,
        {'query_text': 'SELECT id, title, body FROM notes ORDER BY id', 'row_limit': 10},
        {'connection': connection_payload['connection']},
    )

    assert connection_payload['connection']['engine'] == 'sqlite'
    assert len(query_payload['records']) == 2
    assert query_payload['records'][0]['title'] == 'Alpha'
    assert 'First row' in query_payload['documents'][0]['text']


def test_database_query_rejects_non_read_only_statements(tmp_path: Path) -> None:
    database_path = tmp_path / 'unsafe.sqlite'
    with sqlite3.connect(database_path) as connection:
        connection.execute('CREATE TABLE notes (id INTEGER PRIMARY KEY, title TEXT)')
        connection.commit()

    connection_payload = node_registry.execute(
        'DATABASE_CONNECTION',
        1,
        {'engine': 'sqlite', 'file_path': str(database_path), 'connect_timeout_s': 5},
        {},
    )

    try:
        node_registry.execute(
            'DATABASE_QUERY',
            1,
            {'query_text': 'DELETE FROM notes', 'row_limit': 10},
            {'connection': connection_payload['connection']},
        )
    except ValueError as exc:
        assert 'read-only' in str(exc)
    else:
        raise AssertionError('Expected read-only validation failure for DELETE statement')
